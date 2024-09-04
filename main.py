import os
import json
import requests
from tkinter import *
from tkinter import messagebox, ttk
import pydirectinput
import cv2
import torch
import pyautogui
import threading
import time
import webbrowser
import win32gui
from PIL import ImageGrab, Image
from ultralytics import YOLO
import numpy as np
import base64
import pandas as pd
from io import StringIO
import random
import string
import win32con
from datetime import datetime, timedelta
import subprocess

def get_windows_sid():
    """Windows kullanıcısının SID'sini döner."""
    try:
        result = subprocess.check_output("wmic useraccount where name='%username%' get sid", shell=True)
        sid = result.decode().split("\n")[1].strip()  # SID'yi ayıkla
        return sid
    except Exception as e:
        print(f"SID alınamadı: {e}")
        return None

# Bilgisayar adını alma
computer_name = os.environ['COMPUTERNAME']

# GitHub'daki JSON dosyasının URL'si ve API erişim bilgileri
gist_url = "https://api.github.com/gists/08c5ecb96d01398444f95619349d113f"
gist_token = "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"  # GitHub kişisel erişim tokenı
gist_filename = "keys.txt"  # Gist içinde kullanılan dosya adı

# Key'in süresini belirleyen fonksiyon
def calculate_expiry_time(key_name):
    """Key adından expire süresini hesaplar ve Unix timestamp olarak döner."""
    if key_name.startswith("1DAY"):
        return int(time.time()) + 24 * 60 * 60  # 24 saat
    elif key_name.startswith("3DAY"):
        return int(time.time()) + 3 * 24 * 60 * 60  # 72 saat (3 gün)
    elif key_name.startswith("1MONTH"):
        return int(time.time()) + 30 * 24 * 60 * 60  # 30 gün (1 ay)
    else:
        return None  # Belirtilen bir süre yoksa `None` döner

# Ekran görüntüsü alma ve ön işleme fonksiyonları
def take_screenshot():
    # Ekran görüntüsünü alın
    screenshot = ImageGrab.grab()
    screenshot_np = np.array(screenshot)

    # RGB'den BGR'ye dönüştürme (OpenCV'nin renk formatına uygun)
    screenshot_bgr = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)

    return screenshot_bgr

def preprocess_image(image):
    # Görüntüyü gri tonlamaya çevir
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Gürültüyü azaltmak için Gaussian Blur uygulayın
    blurred_image = cv2.GaussianBlur(gray_image, (5, 5), 0)

    # Görüntüyü daha net hale getirmek için eşikleme (thresholding) yapın
    _, thresholded_image = cv2.threshold(blurred_image, 128, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return thresholded_image

# Görüntü eşleştirme fonksiyonu
def locate_image(image_path, threshold=0.8):
    try:
        screenshot = take_screenshot()

        # Ekran görüntüsünü işleyin
        processed_screenshot = preprocess_image(screenshot)

        # Şablon görüntüsünü yükleyin ve işleyin
        template = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

        if template is None:
            print(f"{image_path} dosyası bulunamadı.")
            return None

        # Şablon ve ekran görüntüsü boyutlarını kontrol edin
        if template.shape[0] > processed_screenshot.shape[0] or template.shape[1] > processed_screenshot.shape[1]:
            print(f"Hata: {image_path} boyut olarak ekran görüntüsünden büyük.")
            return None

        # Eşleşmeyi gerçekleştirin
        result = cv2.matchTemplate(processed_screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            # Bulunan konumu biraz sağ alt köşeye kaydır
            adjusted_location = (max_loc[0] + template.shape[1] // 2, max_loc[1] + template.shape[0] // 2)
            return adjusted_location
        return None
    except Exception as e:
        print(f"Görüntü eşleştirme sırasında bir hata oluştu: {e}")
        return None

def move_and_click(location, button='left'):
    """pyautogui kullanarak fareyi verilen konuma anında götürür ve ardından tıklama yapar."""
    try:
        pyautogui.moveTo(location[0], location[1])  # Fareyi anında taşı
        time.sleep(0.2)  # Kısa bir bekleme süresi
        if button == 'left':
            pyautogui.click()  # Sol tıklama
        elif button == 'right':
            pyautogui.click(button='right')  # Sağ tıklama

        time_to_wait = int(window_instance.cut_time_spinbox.get())
        total_wait_time = time_to_wait + 0.2  # Bekleme süresini hesaba katıyoruz
        time.sleep(total_wait_time)  # Toplam bekleme süresi
    except Exception as e:
        print(f"Fare tıklama işlemi sırasında bir hata oluştu: {e}")

# Gist verilerini alma fonksiyonu
def get_gist_data():
    try:
        headers = {"Authorization": f"token {gist_token}"}
        response = requests.get(gist_url, headers=headers)
        response.raise_for_status()  # HTTP hatalarını yakalar
        gist_data = response.json()
        return json.loads(gist_data["files"][gist_filename]["content"])
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Hata", f"Veri çekilemedi: {e}")
        return {}
    except json.JSONDecodeError as e:
        messagebox.showerror("Hata", f"JSON çözümleme hatası: {e}")
        return {}

# Gist verilerini güncelleme fonksiyonu
def update_gist_data(key_bindings):
    try:
        headers = {"Authorization": f"token {gist_token}"}
        updated_content = {
            "files": {
                gist_filename: {
                    "content": json.dumps(key_bindings, indent=4)
                }
            }
        }
        response = requests.patch(gist_url, headers=headers, json=updated_content)
        response.raise_for_status()  # HTTP hatalarını yakalar
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Hata", f"Gist güncellenirken hata oluştu: {e}")
        return False

def save_key_to_file(key):
    encoded_key = base64.b64encode(key.encode('utf-8')).decode('utf-8')
    with open("user.txt", "w") as f:
        f.write(encoded_key)

def load_key_from_file():
    if os.path.exists("user.txt"):
        with open("user.txt", "r") as f:
            encoded_key = f.read().strip()
            return base64.b64decode(encoded_key).decode('utf-8')
    return None

# Key doğrulama fonksiyonu
def check_key():
    global window_instance

    user_key = key_entry.get().strip()  # Kullanıcının girdiği key'i al
    if not user_key:
        messagebox.showerror("Hata", "Key girmelisiniz!")
        return
    
    key_bindings = get_gist_data()

    if user_key in key_bindings:
        current_time = int(time.time())  # Mevcut Unix timestamp
        key_data = key_bindings[user_key]

        # Kullanıcının SID'sini al
        sid = get_windows_sid()
        if not sid:
            messagebox.showerror("Hata", "Windows SID alınamadı!")
            return

        # Eğer key ilk kez kullanılıyorsa veya expire time yoksa, expire time ayarla
        if key_data["expiry_time"] is None:
            print(f"Key süresi daha önce ayarlanmamış, {user_key} için süre ayarlanıyor.")
            expiry_time = calculate_expiry_time(user_key)
            
            if expiry_time is None:
                messagebox.showerror("Hata", "Geçersiz key süresi!")
                return
            
            # Key süresini ve kullanıcıyı ayarla (SID'yi `user` kısmına kaydediyoruz)
            key_data["user"] = sid
            key_data["expiry_time"] = expiry_time
            key_data["expiry_date"] = datetime.fromtimestamp(expiry_time).strftime("%d.%m.%Y %H:%M")

            if update_gist_data(key_bindings):  # Gist'e kaydet
                save_key_to_file(user_key)
                remaining_time_str = "24 saat" if user_key.startswith("1DAY") else "72 saat" if user_key.startswith("3DAY") else "1 ay"
                messagebox.showinfo("Başarılı", f"Key doğrulandı, kalan süre: {remaining_time_str}")
                root.destroy()
                main_window = Tk()
                window_instance = Window(master=main_window)
                main_window.mainloop()
            else:
                messagebox.showerror("Hata", "Gist güncellenirken bir hata oluştu.")
        elif key_data["user"] == sid:
            # Kalan süreyi hesapla
            expiry_time = key_data["expiry_time"]
            if current_time > expiry_time:
                messagebox.showerror("Hata", "Bu key'in süresi dolmuş.")
            else:
                remaining_time = expiry_time - current_time
                days, rem = divmod(remaining_time, 86400)
                hours, rem = divmod(rem, 3600)
                minutes, seconds = divmod(rem, 60)
                remaining_time_str = f"{days} gün, {hours} saat, {minutes} dakika, {seconds} saniye"

                save_key_to_file(user_key)
                messagebox.showinfo("Başarılı", f"Key doğrulandı, kalan süre: {remaining_time_str}")
                root.destroy()

                # Ana uygulamayı başlat
                main_window = Tk()
                window_instance = Window(master=main_window)
                main_window.mainloop()
        else:
            messagebox.showerror("Hata", "Bu key başka bir SID ile kullanılmış!")
    else:
        messagebox.showerror("Hata", "Key hatalı, lütfen tekrar deneyin.")

def auto_login():
    saved_key = load_key_from_file()
    if saved_key:
        key_entry.insert(0, saved_key)

# YOLOv8 nesne tespit ve ekran yakalama sınıfları
class ekranYakala:
    def __init__(self, window_name):
        self.hwnd = win32gui.FindWindow(None, window_name)
        if not self.hwnd:
            raise Exception('Pencere bulunamadı: {}'.format(window_name))
        window_rect = win32gui.GetWindowRect(self.hwnd)
        self.w = window_rect[2] - window_rect[0]
        self.h = window_rect[3] - window_rect[1]
        self.cropped_x = window_rect[0]
        self.cropped_y = window_rect[1]

    def get_screenshot(self):
        img = ImageGrab.grab(bbox=(self.cropped_x, self.cropped_y, self.cropped_x + self.w, self.cropped_y + self.h))
        img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        return img

    def get_screen_position(self, x, y):
        return (self.cropped_x + x, self.cropped_y + y)

class Window(Frame):
    def __init__(self, master=None, saniye=0):
        Frame.__init__(self, master)
        self.master = master
        self.saniye = saniye

        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        # YOLOv8 model yolunu burada belirtin
        self.model_path = (r"C:\VENV\models\metin.pt")  # Buraya kendi modelinizin yolunu yazın
        self.model = YOLO(self.model_path).to(self.device)

        # Tespit edilen nesneler için boş bir liste
        self.detected_objects = []

        self.detection_thread = None   # Detection thread referansı
        self.detection_pause = False  # Detection durdurma kontrolü
        self.detection_lock = threading.Lock()  # Detection pause için kilit

        self.init_ui()

        # Pencere adını her saniye rastgele değiştirmek için bir zamanlayıcı başlatın
        self.update_window_title()

    def update_window_title(self):
    # Pencere adları listesi
        window_titles = ["VXZ PROJECT"]  # İstediğiniz adları buraya yazın
    
    # Mevcut başlık indeksini saklamak için bir özellik ekleyin
        if not hasattr(self, 'title_index'):
            self.title_index = 0

    # Pencere başlığını değiştirin
        self.master.title(window_titles[self.title_index])

    # Bir sonraki başlığa geçin (döngüsel olarak)
        self.title_index = (self.title_index + 1) % len(window_titles)

    # 5 dakika (300000 ms) sonra başlığı tekrar değiştir
        self.master.after(30000, self.update_window_title)

    def init_ui(self):
        self.master.geometry("500x300")
        self.master.configure(bg='#2C2F33')  # Arka plan rengini koyu gri yap
        self.master.resizable(False, False)

        # Frame'ler
        F1 = Frame(self.master, bg='#23272A')
        F1.place(x=350, y=50)

        F2 = LabelFrame(self.master, text="Durum", font=("Arial", 12, "bold"), fg="white", bg='#2C2F33')
        F2.place(x=20, y=150, width=450, height=100)

        F3 = LabelFrame(self.master, text="Ayarlar", font=("Arial", 12, "bold"), fg="white", bg='#2C2F33')
        F3.place(x=20, y=20, width=300, height=120)

        # Başla ve Durdur Butonları
        self.start_button = Button(F1, text="Başla", command=self.start_detection, width=10, bg="#43B581", fg="white", font=("Arial", 10, "bold"))
        self.start_button.grid(row=0, column=0, padx=5, pady=5)

        self.stop_button = Button(F1, text="Durdur", command=self.stop_detection, width=10, bg="#F04747", fg="#FFC0C0", font=("Arial", 10, "bold"), state=DISABLED)
        self.stop_button.grid(row=1, column=0, padx=5, pady=5)

        # Durum Bilgileri için iki ayrı Label
        self.status_text_label = Label(F2, text="Durum:", font=("Arial", 10, "bold"), fg="white", bg='#2C2F33')
        self.status_label = Label(F2, text="Deaktif", font=("Arial", 10), fg="#993333", bg='#2C2F33')

        self.status_text_label.place(x=10, y=10)
        self.status_label.place(x=70, y=10)

        self.detected_label = Label(F2, text="Tespit Edilen Nesne Sayısı: 0", font=("Arial", 10), fg="white", bg='#2C2F33')
        self.detected_label.place(x=10, y=40)

        # Ayarlar
        Label(F3, text="Pencere Seç:", font=("Arial", 10), fg="white", bg='#2C2F33').grid(row=0, column=0, padx=(5, 0), pady=5, sticky=W)
        self.window_combo = ttk.Combobox(F3, state="readonly", width=21)
        self.window_combo.grid(row=0, column=1, padx=(5, 0), pady=5)

        # Pencere listesini otomatik yenileme
        self.auto_refresh_windows()

        Label(F3, text="Kesme Süresi (sn):", font=("Arial", 10), fg="white", bg='#2C2F33').grid(row=1, column=0, padx=5, pady=5, sticky=W)
        self.cut_time_spinbox = Spinbox(F3, from_=1, to=30, width=5)
        self.cut_time_spinbox.grid(row=1, column=1, padx=5, pady=5, sticky=W)
        self.cut_time_spinbox.delete(0, "end")
        self.cut_time_spinbox.insert(0, "5")  # Varsayılan değer

        # Link
        me = Label(self.master, text="yigit911 | Yoshimura.", fg="#7289DA", cursor="hand2", font="Verdana 7 bold", bg='#2C2F33')
        me.place(x=350, y=260)
        me.bind("<Button-1>", lambda e: webbrowser.open_new("https://discord.com/404"))

        # Değişkenler
        self.detecting = False
        self.detected_count = 0
        self.last_click_time = time.time()  # Son tıklama zamanı

    def refresh_windows(self):
        window_list = []

        def enum_handler(hwnd, result):
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                if window_title:
                    window_list.append(window_title)

        win32gui.EnumWindows(enum_handler, None)
        self.window_combo['values'] = window_list

    def auto_refresh_windows(self):
        selected_window = self.window_combo.get()
        self.refresh_windows()

        if selected_window in self.window_combo['values']:
            self.window_combo.set(selected_window)
        
        self.master.after(3500, self.auto_refresh_windows)  # 3500ms sonra tekrar çalıştır

    def start_detection(self):
        if not self.window_combo.get():
            messagebox.showwarning("Uyarı", "Lütfen bir pencere seçin!")
            return

        self.detecting = True
        self.start_button.config(state=DISABLED)
        self.stop_button.config(state=NORMAL)

        # Durumu güncelle
        self.status_text_label.config(text="Durum:")
        self.status_label.config(text="Aktif", fg="#00FF00")  # Aktif durumu yeşil renkte

        self.screen_capture = ekranYakala(self.window_combo.get())

        # Nesne Tespiti Thread'i
        self.detection_thread = threading.Thread(target=self.detect_objects)
        self.detection_thread.start()

    def stop_detection(self):
        self.detecting = False
        self.start_button.config(state=NORMAL)
        self.stop_button.config(state=DISABLED)

        # Durumu güncelle
        self.status_text_label.config(text="Durum:")
        self.status_label.config(text="Deaktif", fg="#993333")  # Pasif durumu kırmızı/bordo renkte

    def detect_objects(self):

        while self.detecting:
            with self.detection_lock:
                if self.detection_pause:
                    continue

            # Ekran görüntüsünü alın
            screenshot = self.screen_capture.get_screenshot()

            # YOLO ile ekran görüntüsünü işleyin
            results = self.model(screenshot)

            if not any(results):
                # Eğer tespit edilen bir şey yoksa 'q' tuşuna bas
                pydirectinput.keyDown("q")
                time.sleep(0.4)
                pydirectinput.keyUp("q")
                time.sleep(0.8)

            detected_boxes = []  # Tespit edilen kutuları saklamak için liste

            # Kutu içine alma işlemi
            for result in results:
                boxes = result.boxes.xyxy
                if len(boxes) > 0:
                    for box in boxes:
                        x1, y1, x2, y2 = box.int().tolist()
                        detected_boxes.append((x1, y1, x2, y2))
                        # Kutu çizme işlemi
                        cv2.rectangle(screenshot, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # İşlenmiş ekran görüntüsünü Comet'e gönderin
            screenshot_rgb = cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB)  # RGB formatına dönüştür
            screenshot_pil = Image.fromarray(screenshot_rgb)  # PIL formatına dönüştür

            # 45 fps hızında çalışırken her 5 saniyede bir rastgele bir kutuya tıklayın
            current_time = time.time()
            time_to_wait = int(window_instance.cut_time_spinbox.get())
            if detected_boxes and current_time - self.last_click_time >= time_to_wait:
                random_box = random.choice(detected_boxes)
                center_x = (random_box[0] + random_box[2]) // 2
                center_y = (random_box[1] + random_box[3]) // 2
                screen_x, screen_y = self.screen_capture.get_screen_position(center_x, center_y)

                pyautogui.keyDown('shift')
                time.sleep(0.3)
                # Fareyi tespit edilen rastgele bir nesnenin merkezine taşı ve sağ tıkla
                move_and_click((screen_x, screen_y), button='right')
                pyautogui.keyUp('shift')

                self.last_click_time = current_time  # Son tıklama zamanını güncelle

            time.sleep(1/60)  # 60 fps hızında çalıştırma

# Tkinter arayüzü oluştur
root = Tk()
root.title("VXZ PROJECT")
root.geometry("300x150")
root.resizable(False, False)
root.configure(bg='#2C2F33')  # Arka plan rengini koyu gri yap

# Key girişi için label ve entry
label = Label(root, text="Lütfen Key'inizi Girin:", fg="white", bg='#2C2F33')
label.pack(pady=10)

key_entry = Entry(root, width=30, bg='#23272A', fg="white", insertbackground="white")
key_entry.pack()

# Key kontrol butonu
check_button = Button(root, text="Kabul Et", command=check_key, bg="#43B581", fg="white")
check_button.pack(pady=10)

# Uygulama açıldığında otomatik key kontrolü
auto_login()

root.mainloop()
