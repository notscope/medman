import os
from tqdm import tqdm
from hashing import hash_file_sha256, hash_image_phash, hash_video_frames, compare_video_hashes, hash_fingerprint_parallel, hash_file_parallel, hash_image_parallel, hash_video_parallel
from move_files import move_to_duplicates, print_action
from scoring import score_image, score_video
from metadata import get_image_metadata, get_video_metadata

# --- CLUSTERING UTILITIES ---

class UnionFind:
    def __init__(self):
        self.parent = {}
    def find(self, x):
        if self.parent.setdefault(x, x) != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]
    def union(self, x, y):
        rx, ry = self.find(x), self.find(y)
        if rx != ry:
            self.parent[ry] = rx

def cluster_images(image_paths, threshold, sha_workers=8, phash_workers=8, progress_callback=None):
    """
    Cluster images with a multi-stage approach for speed and accuracy:
    1) Fingerprint (Size + MD5 of ends) to group potential candidates
    2) Full SHA-256 to split fingerprint groups into bit-identical sets
    3) Parallel pHash for representatives of each SHA group
    """
    def sub_cb(stage_name):
        if not progress_callback: return None
        def cb(curr, tot):
            progress_callback(f"{stage_name}: {curr}/{tot}", curr, tot)
        return cb

    # 1) Fingerprint groups in parallel
    fingerprints = hash_fingerprint_parallel(image_paths, max_workers=sha_workers, progress_callback=sub_cb("Fingerprinting"))
    fp_map = {}
    for path, fp in fingerprints.items():
        fp_map.setdefault(fp, []).append(path)

    # 2) Refine fingerprint groups with Full SHA-256
    # Only need SHA for files that share a fingerprint
    to_sha = []
    for paths in fp_map.values():
        if len(paths) > 1:
            to_sha.extend(paths)
    
    sha_results = hash_file_parallel(to_sha, max_workers=sha_workers, progress_callback=sub_cb("SHA Hashing"))
    
    # Final exact groups (SHA-256 as key)
    # For files with unique fingerprints, we use path as unique key
    exact_map = {}
    for path, fp in fingerprints.items():
        if path in sha_results:
            key = sha_results[path]
        else:
            key = f"unique_{path}"
        exact_map.setdefault(key, []).append(path)

    uf = UnionFind()
    
    # 3) Representatives for perceptual hash
    # We only need to check one file per exact SHA group
    reps = [paths[0] for paths in exact_map.values()]
    # Parallel pHash (using ProcessPool)
    phash_results = hash_image_parallel(reps, max_workers=phash_workers, progress_callback=sub_cb("pHash"))
    
    # 4) Compare perceptual hashes pairwise
    reps_valid = list(phash_results.keys())
    n = len(reps_valid)
    for i in tqdm(range(n), desc="Comparing images"):
        p1 = reps_valid[i]
        h1 = phash_results[p1]
        for j in range(i+1, n):
            p2 = reps_valid[j]
            h2 = phash_results[p2]
            sim = 1 - (h1 - h2) / 64.0
            if sim >= threshold:
                uf.union(p1, p2)

    # 5) Build clusters
    clusters = {}
    for paths in exact_map.values():
        rep = paths[0]
        root = uf.find(rep)
        clusters.setdefault(root, []).extend(paths)

    return [group for group in clusters.values() if len(group) > 1]

def cluster_videos(video_paths, threshold, sample_count, sha_workers=8, phash_workers=8, progress_callback=None):
    """
    Cluster videos with a multi-stage approach for speed and accuracy.
    """
    def sub_cb(stage_name):
        if not progress_callback: return None
        def cb(curr, tot):
            progress_callback(f"{stage_name}: {curr}/{tot}", curr, tot)
        return cb

    # 1) Fingerprint groups
    fingerprints = hash_fingerprint_parallel(video_paths, max_workers=sha_workers, progress_callback=sub_cb("Fingerprinting"))
    fp_map = {}
    for path, fp in fingerprints.items():
        fp_map.setdefault(fp, []).append(path)

    # 2) Refine with Full SHA-256
    to_sha = []
    for paths in fp_map.values():
        if len(paths) > 1:
            to_sha.extend(paths)
    
    sha_results = hash_file_parallel(to_sha, max_workers=sha_workers, progress_callback=sub_cb("SHA Hashing"))
    
    exact_map = {}
    for path, fp in fingerprints.items():
        if path in sha_results:
            key = sha_results[path]
        else:
            key = f"unique_{path}"
        exact_map.setdefault(key, []).append(path)

    uf = UnionFind()

    # 3) Representatives for video hash
    reps = [paths[0] for paths in exact_map.values()]
    vhash_results = hash_video_parallel(reps, sample_count, max_workers=phash_workers, progress_callback=sub_cb("Video pHash"))
    
    # 4) Compare video hashes pairwise
    reps_valid = list(vhash_results.keys())
    n = len(reps_valid)
    for i in tqdm(range(n), desc="Comparing videos"):
        p1 = reps_valid[i]
        h1 = vhash_results[p1]
        for j in range(i+1, n):
            p2 = reps_valid[j]
            h2 = vhash_results[p2]
            sim = compare_video_hashes(h1, h2)
            if sim >= threshold:
                uf.union(p1, p2)

    # 5) Build clusters
    clusters = {}
    for paths in exact_map.values():
        rep = paths[0]
        root = uf.find(rep)
        clusters.setdefault(root, []).extend(paths)

    return [group for group in clusters.values() if len(group) > 1]


# --- HANDLERS FOR CLUSTERS ---

def handle_image_cluster(cluster, interactive, duplicates_dir, cluster_index, cluster_total):
    scored = sorted([(score_image(p), p) for p in cluster], reverse=True)
    best = [scored[0][1]]  # mutable container holding current best
    others = [p for _, p in scored[1:]]
    for other in others:
        if not os.path.exists(best[0]) or not os.path.exists(other):
            continue
        # Check exact SHA first
        sha_best = hash_file_sha256(best[0])
        sha_other = hash_file_sha256(other)
        if sha_best is not None and sha_best == sha_other:
            # exact duplicate → auto-move other without GUI
            dest = move_to_duplicates(other, duplicates_dir)
            print_action("SHA", other, dest)
            continue

        if interactive:
            # compute metadata and perceptual similarity
            meta_best = get_image_metadata(best[0])
            meta_other = get_image_metadata(other)
            h1 = hash_image_phash(best[0])
            h2 = hash_image_phash(other)
            if h1 is None or h2 is None:
                sim = 0.0
            else:
                sim = 1 - (h1 - h2) / 64.0
            
            if sim < threshold:
                # Pair doesn't meet perceptual threshold, skip comparison
                continue

            # define handler to possibly update best
            def make_handler(b_list, o):
                def handler(decision):
                    if decision == 'left':
                        # keep best: remove other
                        dest = move_to_duplicates(o, duplicates_dir)
                        print_action("PHASH", o, dest)
                    elif decision == 'right':
                        # keep other: remove best, update best
                        dest = move_to_duplicates(b_list[0], duplicates_dir)
                        print_action("PHASH", b_list[0], dest)
                        b_list[0] = o
                    elif decision in ('both', 'skip'):
                        pass
                    elif decision == 'quit':
                        exit()
                return handler
            
            handler = make_handler(best, other)
            
            try:
                from gui.window import review_image_pair
                review_image_pair(best[0], other, meta_best, meta_other, sim, handler, cluster_index=cluster_index, cluster_total=cluster_total)
            except (ImportError, RuntimeError, tk.TclError) if 'tk' in globals() else (ImportError, RuntimeError):
                # Fallback to simple CLI prompt if GUI fails
                print(f"\n[INTERACTIVE] Reviewing Cluster {cluster_index}/{cluster_total}")
                print(f"Similarity: {sim*100:.1f}%")
                print(f"Left: {best[0]} ({meta_best[0][0]}x{meta_best[0][1]})")
                print(f"Right: {other} ({meta_other[0][0]}x{meta_other[0][1]})")
                choice = input("Choice ( [A] Keep Left / [D] Keep Right / [W] Keep Both / [S] Skip / [Q] Quit ): ").lower()
                decision_map = {'a': 'left', 'd': 'right', 'w': 'both', 's': 'skip', 'q': 'quit'}
                handler(decision_map.get(choice, 'skip'))
            except Exception as e:
                 print(f"[ERROR] GUI review failed: {e}. Skipping interactive review for this pair.")
        else:
            # automatic: move other
            dest = move_to_duplicates(other, duplicates_dir)
            print_action("AUTO_IMG", other, dest)


def handle_video_cluster(cluster, interactive, duplicates_dir, sample_count, cluster_index, cluster_total):
    scored = sorted([(score_video(p), p) for p in cluster], reverse=True)
    best = [scored[0][1]]
    others = [p for _, p in scored[1:]]
    for other in others:
        if not os.path.exists(best[0]) or not os.path.exists(other):
            continue
        # Exact-SHA check
        sha_best = hash_file_sha256(best[0])
        sha_other = hash_file_sha256(other)
        if sha_best is not None and sha_best == sha_other:
            dest = move_to_duplicates(other, duplicates_dir)
            print_action("SHA", other, dest)
            continue

        if interactive:
            meta_best = get_video_metadata(best[0])
            meta_other = get_video_metadata(other)
            # perceptual similarity
            vhash_best = hash_video_frames(best[0], sample_count)
            vhash_other = hash_video_frames(other, sample_count)
            sim = compare_video_hashes(vhash_best, vhash_other)
            
            if sim < threshold:
                # Pair doesn't meet perceptual threshold, skip comparison
                continue

            def make_handler(b_list, o):
                def handler(decision):
                    if decision == 'left':
                        dest = move_to_duplicates(o, duplicates_dir)
                        print_action("VIDHASH", o, dest)
                    elif decision == 'right':
                        dest = move_to_duplicates(b_list[0], duplicates_dir)
                        print_action("VIDHASH", b_list[0], dest)
                        b_list[0] = o
                    elif decision in ('both', 'skip'):
                        pass
                    elif decision == 'quit':
                        exit()
                return handler
            
            handler = make_handler(best, other)
            
            try:
                from gui.window import review_video_pair
                review_video_pair(best[0], other, meta_best, meta_other, sim, handler, cluster_index=cluster_index, cluster_total=cluster_total)
            except (ImportError, RuntimeError):
                # Fallback to CLI
                print(f"\n[INTERACTIVE] Reviewing Video Cluster {cluster_index}/{cluster_total}")
                print(f"Similarity: {sim*100:.1f}%")
                print(f"Left: {best[0]} ({meta_best[0][0]}x{meta_best[0][1]}, {meta_best[1]:.1f}s)")
                print(f"Right: {other} ({meta_other[0][0]}x{meta_other[0][1]}, {meta_other[1]:.1f}s)")
                choice = input("Choice ( [A] Keep Left / [D] Keep Right / [W] Keep Both / [S] Skip / [Q] Quit ): ").lower()
                decision_map = {'a': 'left', 'd': 'right', 'w': 'both', 's': 'skip', 'q': 'quit'}
                handler(decision_map.get(choice, 'skip'))
            except Exception as e:
                print(f"[ERROR] GUI review failed: {e}. Skipping interactive review for this pair.")
        else:
            dest = move_to_duplicates(other, duplicates_dir)
            print_action("AUTO_VID", other, dest)