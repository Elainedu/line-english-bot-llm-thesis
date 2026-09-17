from PyPDF2 import PdfReader, PdfWriter

# 開啟原始 PDF
reader = PdfReader("02LINE Bot結合大型語言模型之英語學習系統設計與實作.docx.pdf")
writer = PdfWriter()

# 取出後面 4 頁（假設總頁數為 80）
for page_num in range(len(reader.pages) - 4, len(reader.pages)):
    writer.add_page(reader.pages[page_num])

# 儲存新 PDF
with open("後面4頁.pdf", "wb") as f:
    writer.write(f)