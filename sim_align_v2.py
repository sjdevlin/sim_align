import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import socket
from flask import Flask, Response, render_template, request
from picamera.array import PiRGBArray
from picamera import PiCamera
from picamera.exc import PiCameraMMALError
import cv2
import numpy as np

def get_local_ip():
    try:
        # Create a socket object
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Use Google's Public DNS server to initiate a connection
        # The connection does not actually occur, but it allows the socket to get the proper IP
        s.connect(("8.8.8.8", 80))
        # Get the socket's own address
        ip = s.getsockname()[0]
        # Close the socket
        s.close()
    except Exception as e:
        ip = "Error: " + str(e)
    return ip

def send_ip():


    # Sender and recipient
    sender_email = "sjdevlin@gmail.com"
    receiver_email = "sjdevlin@gmail.com"
    password = "akun enpw cxtk wuml"  # Your app password

    # Create a multipart message and set headers
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = "Server IP: " + get_local_ip() 

    # Body of the email
    body = "This is an automated email from the SIM Alignment Tool"
    message.attach(MIMEText(body, "plain"))

    # Connect to Gmail's SMTP server
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, message.as_string())
        print("Email sent successfully")
    except Exception as e:
        print(f"Error sending email: {e}")

app = Flask(__name__)

# Send IP address to my email
send_ip()

# Initialize the PiCamera
camera = None
raw_capture = None

def initialize_camera():
    global camera
    global raw_capture
    if camera is not None:
        camera.close()
    try:
        camera = PiCamera()
        camera.resolution = (1232, 1232)
        camera.framerate = 5
        camera.iso = 400
        camera.framerate = 5
        camera.shutter_speed = 100000 # 100ms
        camera.exposure_mode = 'off'
        raw_capture = PiRGBArray(camera, size=(1232, 1232))
    except PiCameraMMALError as e:
        print("Error initializing camera:", e)



@app.route('/')
def index():
    initialize_camera()
    return render_template('video_feed.html')

@app.route('/shutdown', methods=['GET', 'POST'])
def shutdown():
    # Execute shutdown command
    os.system("sudo shutdown -h now")
    return "Shutting down..."



# Function to label connected components
def label_connected_components(binary_image):
    _, labels, stats, centroids = cv2.connectedComponentsWithStats(binary_image, connectivity=8)
    return labels, stats, centroids

def generate_labeled_images():
    for frame in camera.capture_continuous(raw_capture, format="bgr", use_video_port=True):
        image = frame.array[394:826,408:840]

        # Threshold the green channel (BGR) to create a binary mask
        _, green_binary = cv2.threshold(image[:, :, 1], 150, 255, cv2.THRESH_BINARY)

        # Convert the frame to grayscale
        #gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Threshold the grayscale image
        #_, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

        # Label connected components in the binary mask
        labels, stats, centroids = label_connected_components(green_binary)


        # Iterate through the labeled components
        filtered_labels = [label for label in range(1, labels.max() + 1) if stats[label, cv2.CC_STAT_AREA] > 36]

        labelled_spots=np.zeros([2,2])
        label_counter=0

        for label in filtered_labels:

                # Calculate the area and centroid of the component
                area = stats[label, cv2.CC_STAT_AREA]
                centroid_x, centroid_y = centroids[label]
        
                # Draw a bounding box around the component
                x, y, width, height, _ = stats[label]
                #cv2.rectangle(image, (x, y), (x + width, y + height), (0, 255, 0), 2)

                cv2.putText(image, str(width*height), (x, (y - 30)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)        
                # Draw the centroid as a red dot
                cv2.circle(image, (int(centroid_x), int(centroid_y)), 3, (0, 0, 255), -1)

                if label_counter < 2:
                    labelled_spots[label_counter] = centroids[label]
                label_counter += 1
#                print("width: {:.0f} height: {:.0f} x:{:.0f} y:{:.0f}".format(width,height,centroid_x,centroid_y))

        if len(filtered_labels) == 2:
#            print(labelled_spots)
            distance = (np.sqrt( (labelled_spots[0][0] - labelled_spots[1][0]) ** 2 + 
                        (labelled_spots[0][1] - labelled_spots[1][1]) ** 2  )) / 19

            cv2.putText(image,"Spot Sep: {:.1f} mm".format(distance), (50, 400),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)        


 #       else if  len(filtered_labels) == 1:



        # Add overlay grid and encode the labeled image as JPEG
        cv2.circle(image, (216,216), 200, (200, 200, 200), 1)
        cv2.line(image, (216,150), (216,282), (200, 200, 200), 1)
        cv2.line(image, (150,216), (282,216), (200, 200, 200), 1)

        ret, jpeg = cv2.imencode('.jpg', image)

        # Yield the encoded image
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

        # Clear the stream for the next frame
        raw_capture.truncate(0)

@app.route('/video')
def video_feed():
    return Response(generate_labeled_images(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/distance')
def distance():
    return Response(generate_labeled_images(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)
