import customtkinter as ctk
import cv2
import boto3
import time
from PIL import Image, ImageTk

# --- CONFIGURAZIONE ESTETICA ---
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# Palette
COLOR_BG = "#FFFFFF"           
COLOR_PRIMARY = "#6A0DAD"      # Viola Brand
COLOR_SECONDARY = "#A020F0"    
COLOR_ALERT = "#FF0000"        # Rosso Allarme
COLOR_TEXT_MAIN = "#1A1A1A"
COLOR_TEXT_SUB = "#999999"

# Font
FONT_HERO = ("Helvetica", 70, "bold")
FONT_SUB_HERO = ("Helvetica", 28)
FONT_BTN = ("Helvetica", 18, "bold")
FONT_QUESTION = ("Helvetica", 40, "bold") # Per "What are you looking for?"
FONT_WARNING = ("Helvetica", 20, "bold")  # Per l'avviso intruso

# --- CONFIGURAZIONE AWS ---
BUCKET_NAME = "face.reco"
REGION = "eu-west-2"
TARGET_USER_IMAGE = "users/marco.jpg"   # immagine target
SIMILARITY_THRESHOLD = 90.0

class MarcoSentinel(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Setup Fullscreen
        self.title("Marco's Sentinel")
        self.attributes("-fullscreen", True)
        self.configure(fg_color=COLOR_BG)
        
        # Exit con ESC
        self.bind("<Escape>", lambda e: self.destroy())

        # Variabili
        self.cap = None
        
        # Connessione AWS
        try:
            self.s3 = boto3.client('s3', region_name=REGION)
            self.reko = boto3.client('rekognition', region_name=REGION)
        except Exception as e:
            print(f"Errore AWS: {e}")

        # --- CONTAINER FRAMES ---
        # Creiamo due "pagine": Home e Personal Area
        self.home_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.personal_frame = ctk.CTkFrame(self, fg_color="transparent")

        # Setup Iniziale
        self.setup_home()
        self.show_frame("home")

    # --- SETUP GRAFICA HOME ---
    def setup_home(self):
        # Card Centrale
        self.card = ctk.CTkFrame(self.home_frame, fg_color="transparent")
        self.card.place(relx=0.5, rely=0.5, anchor="center")

        # Loghi
        ctk.CTkLabel(self.card, text="simply.", font=FONT_SUB_HERO, text_color=COLOR_SECONDARY).pack()
        ctk.CTkLabel(self.card, text="HideIT", font=FONT_HERO, text_color=COLOR_PRIMARY).pack(pady=(0, 60))

        # Bottone ACCEDI
        self.btn_accedi = ctk.CTkButton(
            self.card, 
            text="ACCEDI", 
            command=self.check_environment,
            width=300, height=60,
            corner_radius=30,
            font=FONT_BTN,
            fg_color=COLOR_PRIMARY, hover_color="#4b0082"
        )
        self.btn_accedi.pack()
        
        # Exit
        ctk.CTkButton(self.home_frame, text="✕", command=self.destroy, width=50, height=50, 
                      fg_color="transparent", text_color="gray", font=("Arial", 24)).place(relx=0.97, rely=0.05, anchor="center")

    # --- SETUP GRAFICA PERSONAL AREA (Dinamica) ---
    def setup_personal_area(self, is_intruder=False):
        # Pulisce il frame precedente se c'era roba
        for widget in self.personal_frame.winfo_children():
            widget.destroy()

        content = ctk.CTkFrame(self.personal_frame, fg_color="transparent")
        content.place(relx=0.5, rely=0.5, anchor="center")

        # 1. La Domanda (Appare SEMPRE)
        ctk.CTkLabel(content, text="What are you looking for?", font=FONT_QUESTION, text_color=COLOR_TEXT_MAIN).pack(pady=20)

        # 2. Logica Intruso
        if is_intruder:
            ctk.CTkLabel(content, text="You are not Marco, your face is in the database.", 
                         font=FONT_WARNING, text_color=COLOR_ALERT).pack(pady=(10, 0))
        
        # Tasto per tornare indietro (opzionale, per non rimanere bloccati)
        ctk.CTkButton(self.personal_frame, text="LOGOUT", command=lambda: self.show_frame("home"),
                      fg_color="transparent", text_color="gray", hover_color="#f0f0f0").place(relx=0.5, rely=0.9, anchor="center")

    # --- LOGICA DI SCANSIONE ---
    def check_environment(self):
        self.btn_accedi.configure(state="disabled", text="VERIFICA...")
        self.update()

        # 1. Scatto
        frame = self.take_silent_photo()
        if frame is None:
            self.btn_accedi.configure(state="normal", text="ACCEDI")
            return

        # 2. Analisi
        is_marco = False
        _, buf = cv2.imencode(".jpg", frame)
        photo_bytes = buf.tobytes()

        try:
            response = self.reko.compare_faces(
                SourceImage={'S3Object': {'Bucket': BUCKET_NAME, 'Name': TARGET_USER_IMAGE}},
                TargetImage={'Bytes': photo_bytes},
                SimilarityThreshold=SIMILARITY_THRESHOLD
            )
            if len(response['FaceMatches']) > 0:
                is_marco = True
            
            # Se è un intruso, salviamo la foto SUBITO
            if not is_marco:
                self.save_intruder(photo_bytes)

        except Exception as e:
            print(e) # In caso di errore AWS, trattiamo come intruso/errore ma procediamo

        # 3. Transizione
        # Indipendentemente dal risultato, andiamo alla schermata "What are you looking for?"
        # Ma passiamo il flag is_intruder per decidere se mostrare la scritta rossa.
        self.setup_personal_area(is_intruder=not is_marco)
        self.show_frame("personal")
        
        # Resetta il bottone home per quando tornerai
        self.btn_accedi.configure(state="normal", text="ACCEDI")

    def take_silent_photo(self):
        cap = cv2.VideoCapture(0)
        time.sleep(0.3)
        ret, frame = cap.read()
        cap.release()
        return frame if ret else None

    def save_intruder(self, photo_bytes):
        timestamp = int(time.time())
        filename = f"intruders/WARNING_{timestamp}.jpg"
        try:
            self.s3.put_object(Bucket=BUCKET_NAME, Key=filename, Body=photo_bytes)
            print(f"Intruso archiviato: {filename}")
        except:
            pass

    # --- NAVIGAZIONE ---
    def show_frame(self, name):
        self.home_frame.pack_forget()
        self.personal_frame.pack_forget()

        if name == "home":
            self.home_frame.pack(fill="both", expand=True)
        elif name == "personal":
            self.personal_frame.pack(fill="both", expand=True)

if __name__ == "__main__":
    app = MarcoSentinel()
    app.mainloop()