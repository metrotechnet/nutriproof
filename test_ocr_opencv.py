import cv2
import easyocr

# Path to your image file
def main():
    image_path = 'debug/cell_0_3.png'  # Change to your image file
    # Read image with OpenCV
    image = cv2.imread(image_path)
    if image is None:
        print(f'Could not load image: {image_path}')
        return
    # Convert to RGB (EasyOCR expects RGB)
    # rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    # Calculate scale factor to reduce height to ~40 pixels
    scale = 0.4 # if original height is 100 pixels
    resized = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    # crop image in order to remove pixel on the right and bottom
    h, w = resized.shape[:2]
    resized = resized[2:h-2, 2:w-2]

    # Initialize EasyOCR Reader
    reader = easyocr.Reader(['en', 'fr'])  # Add other languages if needed
    # Run OCR
    results = reader.readtext(resized, detail=2, filter_ths=0.001, min_size=1)

    print('EasyOCR Results:')
    # If no text detected, but a bar contour is found, set detected text to '1'
    if not results:
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        img_height =  resized.shape[0]
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if h > 0.2 * img_height:  # If a large bar is found=
                cv2.rectangle(resized, (x, y), (x+w, y+h), (0,0,255), 2)
                print("Detected bar contour, setting text to '1'")
                print("Text: 1 (Confidence: 1.00)")
                break
   
    inv_scale = 1
    found_text = False
    for bbox, text, conf in results:
        print(f'Text: {text} (Confidence: {conf:.2f})')
        if text.strip():
            found_text = True
        pt1 = (int(bbox[0][0] * inv_scale), int(bbox[0][1] * inv_scale))
        pt2 = (int(bbox[2][0] * inv_scale), int(bbox[2][1] * inv_scale))
        cv2.rectangle(resized, pt1, pt2, (0, 255, 0), 2)



    cv2.imshow('OCR Result', resized)
    cv2.waitKey(0)

if __name__ == '__main__':
    main()
