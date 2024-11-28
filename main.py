from cvzone.HandTrackingModule import HandDetector
import cv2
import os
import numpy as np
import webbrowser
import pytesseract
import threading
import speech_recognition as sr
import queue

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Function to detect URLs using OCR
def find_urls_in_image(img):
    text = pytesseract.image_to_string(img)
    urls = [line for line in text.split('\n') if line.startswith('https')]
    return urls

# Function to calculate the distance between two points
def calculate_distance(x1, y1, x2, y2):
    return np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

commands_queue = queue.Queue()

def async_recognize_command():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening for voice command...")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)
    try:
        command = recognizer.recognize_google(audio).lower()
        print("Voice command recognized:", command)
        commands_queue.put(command)
    except sr.UnknownValueError:
        print("Could not understand the voice command.")
    except sr.RequestError as e:
        print("Could not request results from Google Speech Recognition service; {0}".format(e))

def check_for_commands(imgCurrent):
    while not commands_queue.empty():
        command = commands_queue.get()
        imgCurrent = process_command(command, imgCurrent)
    return imgCurrent

def process_command(command, imgCurrent):
    x, y = 100, 100
    radius = 50
    x1, y1 = 150, 150
    x2, y2 = 250, 250
    color = (0, 255, 0)
    thickness = 2

    if "draw circle" in command:
        cv2.circle(imgCurrent, (x, y), radius, color, thickness)
        print("Circle drawn.")
    elif "draw rectangle" in command:
        cv2.rectangle(imgCurrent, (x1, y1), (x2, y2), color, thickness)
        print("Rectangle drawn.")
    elif "draw line" in command:
        start_point = (50, 300)
        end_point = (300, 300)
        cv2.line(imgCurrent, start_point, end_point, color, thickness)
        print("Line drawn.")
    else:
        print("Command not recognized for drawing.")

    return imgCurrent

# Parameters
width, height = 380, 620
gestureThreshold = 300
folderPath = "Presentation"
pinchThreshold = 40

# Camera Setup
cap = cv2.VideoCapture(0)
cap.set(3, width)
cap.set(4, height)

# Hand Detector
detectorHand = HandDetector(detectionCon=0.8, maxHands=1)

# Variables
imgList = []
delay = 30
buttonPressed = False
counter = 0
drawMode = False
imgNumber = 0
delayCounter = 0
annotations = [[]]
annotationNumber = -1
annotationStart = False
hs, ws = int(height * 0.4), int(width * 1.0)

# Function to resize and maintain aspect ratio
def resize_and_pad(img, size, pad_color=0):
    h, w = img.shape[:2]
    sh, sw = size

    if h > sh or w > sw:
        interp = cv2.INTER_AREA
    else:
        interp = cv2.INTER_CUBIC

    aspect = w / h
    if aspect > 1:
        new_w = sw
        new_h = np.round(new_w / aspect).astype(int)
        pad_vert = (sh - new_h) / 2
        pad_top, pad_bot = np.floor(pad_vert).astype(int), np.ceil(pad_vert).astype(int)
        pad_left, pad_right = 0, 0
    elif aspect < 1:
        new_h = sh
        new_w = np.round(new_h * aspect).astype(int)
        pad_horz = (sw - new_w) / 2
        pad_left, pad_right = np.floor(pad_horz).astype(int), np.ceil(pad_horz).astype(int)
        pad_top, pad_bot = 0, 0
    else:
        new_h, new_w = sh, sw
        pad_left, pad_right, pad_top, pad_bot = 0, 0, 0, 0

    scaled_img = cv2.resize(img, (new_w, new_h), interpolation=interp)
    scaled_img = cv2.copyMakeBorder(scaled_img, pad_top, pad_bot, pad_left, pad_right, cv2.BORDER_CONSTANT,
                                     value=pad_color)

    return scaled_img

# Get list of presentation images
lastImgNumber = -1
pathImages = sorted(os.listdir(folderPath), key=len)
print(pathImages)

while True:
    success, img = cap.read()
    img = cv2.flip(img, 1)
    if lastImgNumber != imgNumber:
        pathFullImage = os.path.join(folderPath, pathImages[imgNumber])
        imgCurrent = cv2.imread(pathFullImage)
        lastImgNumber = imgNumber

    hands, img = detectorHand.findHands(img)
    cv2.line(img, (0, gestureThreshold), (width, gestureThreshold), (0, 255, 0), 10)

    imgDisplay = imgCurrent.copy()


    if hands and buttonPressed is False:
        hand = hands[0]
        fingers = detectorHand.fingersUp(hand)
        lmList = hand["lmList"]

        x_thumb, y_thumb = lmList[4][0], lmList[4][1]
        x_index, y_index = lmList[8][0], lmList[8][1]

        # Next Slide: Little finger up, all other fingers down
        if fingers == [0, 0, 0, 0, 1]:
            print("Next Slide")
            buttonPressed = True
            if imgNumber < len(pathImages) - 1:
                imgNumber += 1
                annotations = [[]]
                annotationNumber = -1
                annotationStart = False

        # Previous Slide: Thumb up, all other fingers down
        elif fingers == [1, 0, 0, 0, 0]:
            print("Previous Slide")
            buttonPressed = True
            if imgNumber > 0:
                imgNumber -= 1
                annotations = [[]]
                annotationNumber = -1
                annotationStart = False


        # Drawing: Index finger up, all other fingers down
        elif fingers == [0, 1, 0, 0, 0]:
            if not annotationStart:
                annotationStart = True
                annotationNumber += 1
                annotations.append([])
            # Append drawing position
            annotations[annotationNumber].append((lmList[8][0], lmList[8][1]))

        # Pinch Gesture to open URL
        distance = calculate_distance(x_thumb, y_thumb, x_index, y_index)
        if distance < pinchThreshold:
            urls = find_urls_in_image(imgCurrent)
            if urls:
                webbrowser.open(urls[0])
                print("URL opened. Press any key to continue the presentation...")
                cv2.waitKey(0)
                buttonPressed = False
                counter = 0

        # General gesture for voice command: All fingers up
        if all(finger == 1 for finger in fingers):
            if not buttonPressed:
                threading.Thread(target=async_recognize_command).start()
                buttonPressed = True
        else:
            buttonPressed = False


    if buttonPressed:
        counter += 1
        if counter > delay:
            counter = 0
            buttonPressed = False

    for i, annotation in enumerate(annotations):
        for j in range(len(annotation)):
            if j != 0:
                cv2.line(imgCurrent, annotation[j - 1], annotation[j], (0, 0, 200), 12)

    imgSmall = cv2.resize(img, (ws, hs))
    h, w, _ = imgCurrent.shape
    imgCurrent[0:hs, w - ws:w] = imgSmall

    cv2.imshow("Presentation", imgCurrent)
    key = cv2.waitKey(1)
    if key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()