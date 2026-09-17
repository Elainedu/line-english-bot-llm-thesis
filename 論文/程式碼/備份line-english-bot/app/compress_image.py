from PIL import Image
import os

# 圖片路徑
original_path = "app/static/rich_menu.png"  # 使用您的圖片實際路徑
compressed_path = "app/static/rich_menu_small.png"

# 打開圖片
try:
    img = Image.open(original_path)
    original_size = os.path.getsize(original_path)
    print(f"原始圖片尺寸: {img.size}")
    print(f"原始檔案大小: {original_size/1024:.2f} KB")
    
    # 調整大小 (維持相同比例但縮小)
    img = img.resize((2500, 1686), Image.LANCZOS)
    
    # 強力壓縮 - 降低品質
    img.save(compressed_path, "PNG", optimize=True, quality=30)
    
    # 檢查壓縮結果
    compressed_size = os.path.getsize(compressed_path)
    print(f"壓縮後大小: {compressed_size/1024:.2f} KB")
    print(f"壓縮率: {compressed_size/original_size*100:.2f}%")
    
    # 如果還是太大，嘗試轉為JPEG格式（犧牲透明度）
    if compressed_size > 1024 * 1024:  # 如果仍大於1MB
        print("PNG壓縮後仍然太大，嘗試轉為JPEG格式...")
        jpeg_path = "app/static/rich_menu_small.jpg"
        
        # 將透明背景轉為白色（JPEG不支持透明度）
        if img.mode in ('RGBA', 'LA'):
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])  # 使用alpha通道作為遮罩
            img = background
        
        # 以較低品質保存為JPEG
        img.save(jpeg_path, "JPEG", optimize=True, quality=65)
        
        jpeg_size = os.path.getsize(jpeg_path)
        print(f"JPEG格式大小: {jpeg_size/1024:.2f} KB")
        print(f"JPEG壓縮率: {jpeg_size/original_size*100:.2f}%")
        
        if jpeg_size <= 1024 * 1024:
            print("成功! JPEG格式小於1MB，可以使用。")
        else:
            print("警告: JPEG格式仍然大於1MB!")
            
except Exception as e:
    print(f"處理圖片時發生錯誤: {e}")