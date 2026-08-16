import docx
from pptx import Presentation

# DOCX
doc = docx.Document()
doc.add_heading('Test Document', 0)
doc.add_paragraph('This is paragraph 1.')
doc.add_paragraph('This is paragraph 2.')
doc.add_paragraph('List item 1', style='List Bullet')
table = doc.add_table(rows=2, cols=2)
table.cell(0,0).text = 'A1'
table.cell(0,1).text = 'B1'
table.cell(1,0).text = 'A2'
table.cell(1,1).text = 'B2'
doc.save('tests/fixtures/test.docx')

# PPTX
prs = Presentation()
slide_layout = prs.slide_layouts[0]
slide1 = prs.slides.add_slide(slide_layout)
slide1.shapes.title.text = "Slide 1"
slide1.placeholders[1].text = "Body 1"

slide_layout = prs.slide_layouts[1]
slide2 = prs.slides.add_slide(slide_layout)
slide2.shapes.title.text = "Slide 2"
slide2.placeholders[1].text = "Body 2"
prs.save('tests/fixtures/test.pptx')
