{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  packages = [
    (pkgs.python312.withPackages (ps: with ps; [
      pip
      numpy
      scipy
      pillow
      pywavelets
      imagehash
      pytesseract
      opencv4
      tqdm
      tkinter
    ]))

    pkgs.tesseract
    pkgs.ffmpeg
  ];
}
