"""Converte instalock_logo.png → instalock_logo.ico para uso no PyInstaller"""
import sys, os
from PIL import Image

src = os.path.join(os.path.dirname(__file__), 'instalock_logo.png')
dst = os.path.join(os.path.dirname(__file__), 'instalock_logo.ico')

img   = Image.open(src).convert('RGBA')
sizes = [(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
imgs  = [img.resize(s, Image.LANCZOS) for s in sizes]
imgs[0].save(dst, format='ICO', sizes=sizes, append_images=imgs[1:])
print(f"ICO gerado: {dst}")