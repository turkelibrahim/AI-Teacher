from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.graphics import renderPDF
from PIL import Image
import pypdf

# 1. Valid text PDF
c = canvas.Canvas('tests/fixtures/test.pdf', pagesize=letter)
c.drawString(100, 750, "Valid Text PDF")
c.drawString(100, 730, "This is page 1.")
c.showPage()
c.drawString(100, 750, "This is page 2.")
c.showPage()
c.save()

# 2. Image-only PDF (Scanned)
# First create a dummy image
img = Image.new('RGB', (100, 100), color = 'red')
img.save('dummy.jpg')

c = canvas.Canvas('tests/fixtures/scanned.pdf', pagesize=letter)
c.drawImage('dummy.jpg', 100, 600, width=100, height=100)
c.showPage()
c.save()

# 3. Encrypted PDF
reader = pypdf.PdfReader('tests/fixtures/test.pdf')
writer = pypdf.PdfWriter()
for page in reader.pages:
    writer.add_page(page)
writer.encrypt('password')
with open('tests/fixtures/encrypted.pdf', 'wb') as f:
    writer.write(f)
