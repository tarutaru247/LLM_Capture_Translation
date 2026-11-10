"""Original geometric app artwork; no external logo or font assets."""
from pathlib import Path
from PIL import Image, ImageDraw


def main():
    root = Path(__file__).resolve().parents[1] / 'resources'
    root.mkdir(exist_ok=True)
    image = Image.new('RGBA', (1024, 1024))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 40, 984, 984), 230, fill='#79E89D')
    draw.rounded_rectangle((185, 220, 735, 645), 110, fill='#154D33')
    draw.polygon([(235, 560), (235, 755), (425, 605)], fill='#154D33')
    draw.rounded_rectangle((440, 485, 850, 800), 85, fill='#F2FFF5')
    draw.polygon([(800, 735), (800, 880), (645, 770)], fill='#F2FFF5')
    draw.line([(290, 390), (600, 390)], fill='#F2FFF5', width=35)
    draw.line([(525, 320), (600, 390), (525, 460)], fill='#F2FFF5', width=35, joint='curve')
    draw.line([(740, 645), (550, 645)], fill='#154D33', width=30)
    draw.line([(610, 590), (550, 645), (610, 700)], fill='#154D33', width=30, joint='curve')
    image.resize((256, 256), Image.Resampling.LANCZOS).save(root / 'icon.png')
    image.save(root / 'icon.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])


if __name__ == '__main__': main()
