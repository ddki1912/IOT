import os
import pickle
import numpy as np
import cv2
import face_recognition
import cvzone
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from firebase_admin import storage
import numpy as np
from datetime import datetime
import urllib

import psutil
from esp.esp32 import *

cred = credentials.Certificate(
    "D:/GitHub/IOT/face_recognition_attendance_window/serviceAccountKey.json"
)
firebase_admin.initialize_app(
    cred,
    {
        "databaseURL": "https://facerecognitiondatabase-ca552-default-rtdb.asia-southeast1.firebasedatabase.app/",
        "storageBucket": "facerecognitiondatabase-ca552.appspot.com",
    },
)

bucket = storage.bucket()

# cap = cv2.VideoCapture(0)

background_img = cv2.imread(
    "D:/GitHub/IOT/face_recognition_attendance_window/resources/background.png"
)

# Import the mode images into a list
mode_folder_path = "D:/GitHub/IOT/face_recognition_attendance_window/resources/mode"
mode_path_list = os.listdir(mode_folder_path)
mode_img_list = []
for path in mode_path_list:
    mode_img_list.append(cv2.imread(os.path.join(mode_folder_path, path)))


mode_type = 0
counter = 0
id = -1

# URL camera frame (192.168.1.24 or 192.168.208.251)
url_low = "http://192.168.1.24/cam-lo.jpg"
url_mid = "http://192.168.1.24/cam-mid.jpg"
url_high = "http://192.168.1.24/cam-hi.jpg"

unlock = False

while True:
    # Get camera frame
    frame = urllib.request.urlopen(url_high)
    img_np = np.array(bytearray(frame.read()), dtype=np.uint8)
    img = cv2.imdecode(img_np, -1)
    img = cv2.resize(img, (640, 480))
    # ret, img = cap.read()

    background_img[44 : 44 + 633, 808 : 808 + 414] = mode_img_list[mode_type]

    small_img = cv2.resize(img, (0, 0), None, fx=0.25, fy=0.25)
    small_img = cv2.cvtColor(small_img, cv2.COLOR_BGR2RGB)

    face_loc_cur_frame = face_recognition.face_locations(small_img)
    encoded_face_cur_frame = face_recognition.face_encodings(
        small_img, face_loc_cur_frame
    )

    background_img[44 : 44 + 633, 808 : 808 + 414] = mode_img_list[mode_type]

    if face_loc_cur_frame:
        # Load the encoded file
        print("Loading encoded file ...")
        with open(
            "D:/GitHub/IOT/face_recognition_attendance_dashboard/train/encoded_file.p", "rb"
        ) as file:
            encoded_known_list_with_ids = pickle.load(file)
            file.close()
        encoded_known_list, student_id_list = encoded_known_list_with_ids
        print(student_id_list)
        print("Encoded file loaded.")

        for encoded_face, face_loc in zip(encoded_face_cur_frame, face_loc_cur_frame):
            matches = face_recognition.compare_faces(encoded_known_list, encoded_face)
            face_dist = face_recognition.face_distance(encoded_known_list, encoded_face)
            match_index = np.argmin(face_dist)

            if face_dist[match_index] <= 40 and matches[match_index]:
                y1, x2, y2, x1 = face_loc
                y1, x2, y2, x1 = y1 * 4, x2 * 4, y2 * 4, x1 * 4

                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)

                id = student_id_list[match_index]
                if counter == 0:
                    cvzone.putTextRect(background_img, "Loading", (300, 400), 2, 1)
                    cv2.imshow("Face Attendance", background_img)
                    cv2.waitKey(1)
                    counter = 1
                    mode_type = 1

        if counter != 0:
            if counter == 1:
                # Get the student info
                student_info = db.reference("student").child(id).get()
                print(student_info)

                # Get the student image
                blob = bucket.get_blob(f"imgs/student/{id}.jpg")
                array = np.frombuffer(blob.download_as_string(), np.uint8)
                student_img = cv2.imdecode(array, cv2.COLOR_BGRA2BGR)
                student_img = cv2.resize(student_img, (216, 216))

                # Update data of attendance
                try:
                    student_attendance = dict(
                        db.reference("class")
                        .child("attendance")
                        .child(datetime.today().strftime("%Y-%m-%d"))
                        .get()
                    )
                except:
                    date = datetime.today().strftime("%Y-%m-%d")
                    data = {f"{date}": {}}

                    students = dict(db.reference("student").get())

                    for key, value in students.items():
                        data[date][key] = ""

                    for key, value in data.items():
                        db.reference("class").child("attendance").child(date).set(value)

                    student_attendance = dict(
                        db.reference("class")
                        .child("attendance")
                        .child(datetime.today().strftime("%Y-%m-%d"))
                        .get()
                    )

                try:
                    if student_attendance[id] == "":
                        attedance_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        db.reference("class").child("attendance").child(
                            datetime.today().strftime("%Y-%m-%d")
                        ).child(id).set(attedance_time)
                    else:
                        mode_type = 3
                        unlock = True
                        counter = 0
                        background_img[44 : 44 + 633, 808 : 808 + 414] = mode_img_list[
                            mode_type
                        ]
                except:
                    db.reference("class").child("attendance").child(
                        datetime.today().strftime("%Y-%m-%d")
                    ).child(id).set(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            if mode_type != 3:
                if 10 < counter < 20:
                    mode_type = 2
                    unlock = True

                background_img[44 : 44 + 633, 808 : 808 + 414] = mode_img_list[
                    mode_type
                ]

                # Render student infomation
                if counter <= 10:
                    cv2.putText(
                        background_img,
                        str(student_info["major"]),
                        (1006, 550),
                        cv2.FONT_HERSHEY_COMPLEX,
                        0.5,
                        (255, 255, 255),
                        1,
                    )
                    cv2.putText(
                        background_img,
                        str(student_info["student_id"]),
                        (1006, 493),
                        cv2.FONT_HERSHEY_COMPLEX,
                        0.5,
                        (255, 255, 255),
                        1,
                    )
                    cv2.putText(
                        background_img,
                        str(student_info["starting_year"]),
                        (1125, 625),
                        cv2.FONT_HERSHEY_COMPLEX,
                        0.6,
                        (100, 100, 100),
                        1,
                    )

                    (w, h), _ = cv2.getTextSize(
                        student_info["name"], cv2.FONT_HERSHEY_COMPLEX, 1, 1
                    )
                    offset = (414 - w) // 2
                    cv2.putText(
                        background_img,
                        str(student_info["name"]),
                        (808 + offset, 445),
                        cv2.FONT_HERSHEY_COMPLEX,
                        1,
                        (50, 50, 50),
                        1,
                    )

                    background_img[175 : 175 + 216, 909 : 909 + 216] = student_img

                counter += 1

                if counter >= 20:
                    counter = 0
                    mode_type = 0
                    student_info = []
                    student_img = []
                    background_img[44 : 44 + 633, 808 : 808 + 414] = mode_img_list[
                        mode_type
                    ]
    else:
        mode_type = 0
        counter = 0

    background_img[162 : 162 + 480, 55 : 55 + 640] = img

    cv2.imshow("Face Attendance", background_img)

    if unlock:
        time.sleep(1)
        send_command("open")
        unlock = False

    if cv2.waitKey(1) & 0xFF == ord("q"):
        unlock = False
        break

cv2.destroyAllWindows()
