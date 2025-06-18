import os
from tqdm import tqdm
from hashing import hash_file_sha256, hash_image_phash, hash_video_frames, compare_video_hashes, hash_file_parallel, hash_image_parallel, hash_video_parallel
from move_files import move_to_duplicates, print_action
from scoring import score_image, score_video
from metadata import get_image_metadata, get_video_metadata
from gui.window import review_image_pair, review_video_pair

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

def cluster_images(image_paths, threshold, sha_workers=8, phash_workers=8):
    """
    Cluster images by SHA and perceptual hash, parallelized with tqdm bars.
    - image_paths: list of file paths
    - threshold: float between 0 and 1
    - sha_workers / phash_workers: thread counts
    """
    # 1) SHA groups in parallel
    sha_results = hash_file_parallel(image_paths, max_workers=sha_workers)
    sha_map = {}
    for path, sha in sha_results.items():
        sha_map.setdefault(sha, []).append(path)

    uf = UnionFind()
    # Union exact duplicates
    for paths in sha_map.values():
        if len(paths) > 1:
            first = paths[0]
            for other in paths[1:]:
                uf.union(first, other)

    # 2) Representatives for perceptual hash
    # We take one representative per sha group
    reps = [paths[0] for paths in sha_map.values()]
    # Compute pHash in parallel
    phash_results = hash_image_parallel(reps, max_workers=phash_workers)
    # Filter out those with None
    phashes = {p: h for p, h in phash_results.items()}

    # 3) Compare perceptual hashes pairwise
    reps_valid = list(phashes.keys())
    n = len(reps_valid)
    # Outer loop with tqdm
    for i in tqdm(range(n), desc="Comparing images"):
        p1 = reps_valid[i]
        h1 = phashes[p1]
        for j in range(i+1, n):
            p2 = reps_valid[j]
            h2 = phashes[p2]
            # compute similarity
            sim = 1 - (h1 - h2) / 64.0
            if sim >= threshold:
                uf.union(p1, p2)

    # 4) Build clusters: include all files in each sha group whose rep falls into a union-find set with size>1
    clusters = {}
    for paths in sha_map.values():
        rep = paths[0]
        if rep in uf.parent:  # has been seen in union-find
            root = uf.find(rep)
            clusters.setdefault(root, []).extend(paths)

    # Return only groups with more than one file
    return [group for group in clusters.values() if len(group) > 1]

def cluster_videos(video_paths, threshold, sample_count, sha_workers=8, phash_workers=8):
    """
    Cluster video files by SHA and perceptual-frame-hash similarity, parallelized.
    - video_paths: list of file paths
    - threshold: similarity threshold (0.0–1.0)
    - sample_count: frames to sample per video
    - sha_workers: threads for SHA
    - phash_workers: processes for video hashing
    """
    # 1) SHA groups in parallel
    sha_results = hash_file_parallel(video_paths, max_workers=sha_workers)
    sha_map = {}
    for path, sha in sha_results.items():
        sha_map.setdefault(sha, []).append(path)

    uf = UnionFind()
    # Union exact duplicates
    for paths in sha_map.values():
        if len(paths) > 1:
            first = paths[0]
            for other in paths[1:]:
                uf.union(first, other)

    # 2) Representatives for perceptual-video hash
    reps = [paths[0] for paths in sha_map.values()]
    # Compute video-frame hashes in parallel
    vhash_results = hash_video_parallel(reps, sample_count, max_workers=phash_workers)
    # Filter only successful
    reps_valid = list(vhash_results.keys())

    # 3) Compare perceptual hashes pairwise
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

    # 4) Build clusters
    clusters = {}
    for paths in sha_map.values():
        rep = paths[0]
        if rep in uf.parent:
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
            review_image_pair(best[0], other, meta_best, meta_other, sim, handler, cluster_index=cluster_index, cluster_total=cluster_total)
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
            review_video_pair(best[0], other, meta_best, meta_other, sim, handler, cluster_index=cluster_index, cluster_total=cluster_total)
        else:
            dest = move_to_duplicates(other, duplicates_dir)
            print_action("AUTO_VID", other, dest)