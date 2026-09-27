#!/usr/bin/env python3
"""Generate a simple icon for the application."""

from PIL import Image, ImageDraw, ImageFont
import os

def create_icon():
    """Create a simple icon for PricePilot."""
    # Create a 256x256 image with a gradient background
    size = 256
    img = Image.new('RGBA', (size, size), (0, 100, 200, 255))
    draw = ImageDraw.Draw(img)
    
    # Draw a simple shopping cart icon
    # Cart body
    draw.rectangle([50, 80, 206, 160], fill=(255, 255, 255, 255), outline=(200, 200, 200, 255), width=3)
    
    # Cart handle
    draw.arc([30, 40, 70, 120], start=0, end=180, fill=(255, 255, 255, 255), width=8)
    
    # Wheels
    draw.ellipse([70, 160, 100, 190], fill=(255, 255, 255, 255))
    draw.ellipse([156, 160, 186, 190], fill=(255, 255, 255, 255))
    
    # Price tag
    draw.polygon([180, 60, 220, 80, 200, 120, 160, 100], fill=(255, 200, 0, 255))
    
    # Save the icon
    icon_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'icon.png')
    img.save(icon_path, 'PNG')
    print(f"Icon created at {icon_path}")

if __name__ == "__main__":
    try:
        from PIL import Image, ImageDraw
        create_icon()
    except ImportError:
        print("PIL not installed. Creating a placeholder instead.")
        # Create a simple SVG icon as fallback
        svg_content = """<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <rect width="256" height="256" fill="#0064C8"/>
  <rect x="50" y="80" width="156" height="80" fill="white" stroke="#CCCCCC" stroke-width="3"/>
  <path d="M 30 40 Q 50 40 50 120" stroke="white" stroke-width="8" fill="none"/>
  <circle cx="85" cy="175" r="15" fill="white"/>
  <circle cx="171" cy="175" r="15" fill="white"/>
  <polygon points="180,60 220,80 200,120 160,100" fill="#FFC800"/>
</svg>"""
        icon_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'icon.svg')
        with open(icon_path, 'w') as f:
            f.write(svg_content)
        print(f"SVG icon created at {icon_path}")
        print("For Electron, you'll need to convert this to PNG using an online tool or ImageMagick")