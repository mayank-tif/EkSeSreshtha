def check_student_id_card_originality(image_file):
    logger.info("StudentHelper : CheckStudentIDCardOriginality : Started")
    
    try:
        from PIL import Image
        import numpy as np
        import io
        
        image_file.seek(0)
        img = Image.open(image_file)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img_array = np.array(img, dtype=np.float32) / 255.0
        gray = np.mean(img_array, axis=2)
        h, w = gray.shape
        
        fft = np.fft.fft2(gray)
        fft_shift = np.fft.fftshift(fft)
        magnitude = np.log(np.abs(fft_shift) + 1)
        cy, cx = h // 2, w // 2
        mask = np.ones_like(magnitude, dtype=bool)
        mask[cy-30:cy+30, cx-30:cx+30] = False
        
        peak_val = np.max(magnitude[mask])
        mean_val = np.mean(magnitude[mask])
        moire_score = peak_val / (mean_val + 1e-6)
        
        if moire_score > 4.0:
            return False, f"Strong moiré pattern detected (score={moire_score:.1f}) - likely screen photo", 0.3
        
        return True, "Basic check passed", 0.5
    except Exception as e:
        return True, f"Check error: {e}", 0.0
