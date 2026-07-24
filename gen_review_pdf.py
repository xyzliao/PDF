#!/usr/bin/env python3
"""Generate a styled PDF book review from markdown."""
import sys
import re
from fpdf import FPDF
import markdown2

class ReviewPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=25)
        
    def header(self):
        pass
    
    def footer(self):
        self.set_y(-15)
        self.set_font('NotoSC', '', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'— {self.page_no()} —', align='C')

    def chapter_title(self, title, size=16):
        self.set_font('NotoSC', 'B', size)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, size * 0.7, title)
        self.ln(4)
    
    def chapter_body(self, text, size=10.5):
        self.set_font('NotoSC', '', size)
        self.set_text_color(40, 40, 40)
        # Process paragraphs
        paragraphs = text.strip().split('\n\n')
        for i, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                continue
            # Handle blockquotes
            if para.startswith('>'):
                lines = para.split('\n')
                quote_text = '\n'.join(l.lstrip('> ').strip() for l in lines if l.strip().startswith('>'))
                self.set_font('NotoSC', '', 9.5)
                self.set_text_color(100, 100, 100)
                x = self.get_x()
                self.set_x(x + 15)
                self.set_font('NotoSC', 'I', 9.5)
                self.multi_cell(self.w - self.l_margin - self.r_margin - 15, 6, quote_text)
                self.set_text_color(40, 40, 40)
                self.ln(3)
                continue
            # Handle horizontal rules
            if para == '---':
                self.ln(2)
                y = self.get_y()
                self.set_draw_color(200, 200, 200)
                self.line(self.l_margin + 30, y, self.w - self.r_margin - 30, y)
                self.ln(4)
                continue
            # Handle images ![alt](path){height=NNmm} or ![alt](path)
            img_match = re.match(r'!\[(.*?)\]\((.*?)\)(?:\{height=(\d+)mm\})?', para.strip())
            if img_match:
                img_path = img_match.group(2).strip()
                img_alt = img_match.group(1).strip()
                custom_h = int(img_match.group(3)) if img_match.group(3) else None
                try:
                    # Calculate image dimensions to fit page width
                    from PIL import Image as PILImage
                    img = PILImage.open(img_path)
                    img_w, img_h = img.size
                    max_w = self.w - self.l_margin - self.r_margin
                    ratio = min(max_w / img_w, 1.0)
                    display_w = img_w * ratio
                    display_h = img_h * ratio
                    # Limit image height: custom or default 90mm
                    max_h = custom_h if custom_h else 90  # mm
                    if display_h > max_h:
                        ratio2 = max_h / display_h
                        display_w *= ratio2
                        display_h *= ratio2
                    x = self.l_margin + (max_w - display_w) / 2
                    self.image(img_path, x=x, w=display_w, h=display_h)
                    self.ln(3)
                except Exception as e:
                    self.set_font('NotoSC', 'I', 9)
                    self.set_text_color(150, 150, 150)
                    self.multi_cell(0, 5, f'[图片: {img_alt}]')
                    self.set_text_color(40, 40, 40)
                    self.ln(2)
                continue
            # Regular paragraph - reduce English word spacing by compressing stretching
            import re as _re
            _has_eng = bool(_re.search(r'[a-zA-Z]{2,}', para))
            if _has_eng:
                self.set_stretching(85)
            self.multi_cell(0, 6.5, para)
            if _has_eng:
                self.set_stretching(100)
            self.ln(2)

def generate_pdf(md_path, pdf_path):
    # Find Chinese font
    import os
    font_paths = [
        '/System/Library/Fonts/STHeiti Medium.ttc',
        '/System/Library/Fonts/PingFang.ttc', 
        '/System/Library/Fonts/Supplemental/Songti.ttc',
        '/System/Library/Fonts/Hiragino Sans GB.ttc',
        '/Library/Fonts/Arial Unicode.ttf',
    ]
    
    font_file = None
    for p in font_paths:
        if os.path.exists(p):
            font_file = p
            break
    
    # Try Noto Sans SC
    noto_paths = [
        '/System/Library/Fonts/Supplemental/NotoSansSC-Regular.otf',
        '/Library/Fonts/NotoSansSC-Regular.otf',
        os.path.expanduser('~/Library/Fonts/NotoSansSC-Regular.otf'),
    ]
    for p in noto_paths:
        if os.path.exists(p):
            font_file = p
            break
    
    if not font_file:
        # Search more broadly
        import glob
        candidates = glob.glob('/System/Library/Fonts/**/*SC*', recursive=True)
        candidates += glob.glob('/System/Library/Fonts/**/*Heiti*', recursive=True)
        candidates += glob.glob('/System/Library/Fonts/**/*PingFang*', recursive=True)
        for c in candidates:
            if c.endswith(('.ttf', '.ttc', '.otf')):
                font_file = c
                break
    
    if not font_file:
        print("ERROR: No Chinese font found!")
        sys.exit(1)
    
    print(f"Using font: {font_file}")
    
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse markdown into sections
    lines = content.split('\n')
    sections = []
    current_section = {'title': '', 'body': '', 'level': 0}
    
    for line in lines:
        if line.startswith('# ') and not line.startswith('## '):
            if current_section['title'] or current_section['body']:
                sections.append(current_section)
            current_section = {'title': line.lstrip('# ').strip(), 'body': '', 'level': 1}
        elif line.startswith('## '):
            if current_section['title'] or current_section['body']:
                sections.append(current_section)
            current_section = {'title': line.lstrip('# ').strip(), 'body': '', 'level': 2}
        else:
            current_section['body'] += line + '\n'
    
    if current_section['title'] or current_section['body']:
        sections.append(current_section)
    
    pdf = ReviewPDF()
    pdf.add_font('NotoSC', '', font_file, uni=True)
    pdf.add_font('NotoSC', 'B', font_file, uni=True)
    pdf.add_font('NotoSC', 'I', font_file, uni=True)
    pdf.add_font('NotoSC', 'BI', font_file, uni=True)
    
    pdf.set_margins(25, 25, 25)
    pdf.add_page()
    
    for section in sections:
        if section['level'] == 1:
            pdf.chapter_title(section['title'], size=18)
        elif section['level'] == 2:
            pdf.ln(4)
            pdf.chapter_title(section['title'], size=14)
        
        if section['body'].strip():
            pdf.chapter_body(section['body'].strip())
    
    pdf.output(pdf_path)
    print(f"PDF saved to: {pdf_path}")

if __name__ == '__main__':
    md_path = sys.argv[1]
    pdf_path = sys.argv[2]
    generate_pdf(md_path, pdf_path)