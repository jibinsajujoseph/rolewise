from fpdf import FPDF

text = "• bullet point\n– en dash\n— em dash\n“smart quotes”\n‘single quotes’"
text = text.replace('•', '-').replace('–', '-').replace('—', '-').replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")

pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", size=11)
pdf.multi_cell(0, 5, text=text)
pdf.output("test.pdf")
print("PDF created successfully")
