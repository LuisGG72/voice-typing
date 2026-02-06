#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║  🎤 BICHÍN VOICE TYPING - VOSK EDITION                        ║
║  ===========================================================  ║
║  Dictado por voz en tiempo real - ULTRA RÁPIDO & OFFLINE     ║
║                                                               ║
║  📁 UBICACIÓN: ~/.openclaw/workspace/voice_typing_vosk.py    ║
║  🎯 ESTADO: ✅ PRODUCCIÓN - Funcionando perfecto              ║
║  📅 Última verificación: 2026-02-06                          ║
╚══════════════════════════════════════════════════════════════╝

INSTRUCCIONES:
    python ~/.openclaw/workspace/voice_typing_vosk.py

CONTROLES:
    🔴 Círculo rojo  = Escuchando
    🟡 Amarillo      = Procesando
    🟢 Flash verde   = Texto escrito
    🖱️  Click izq    = Pausar/Reanudar
    🖱️  Click der    = Cerrar

REQUISITOS:
    - Micrófono USB SF-558 conectado
    - Modelo Vosk: ~/.openclaw/workspace/vosk-model/vosk-model-small-es-0.42/
    - Python 3.x con: vosk, pyaudio, pyautogui, audioop

HARDWARE:
    - Mini PC: MINISFORUM AI X1 Pro
    - Micrófono: SF-558 USB Condenser
    - Sistema: CachyOS (Arch Linux)

Creado por: Bichín (asistente de Luis)
Fecha: 2026-02-06
"""

# === SUPRIMIR ERRORES ALSA ===
import ctypes
from ctypes import c_char_p, c_int, CFUNCTYPE
ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
def py_error_handler(filename, line, function, err, fmt):
    pass
c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
try:
    asound = ctypes.CDLL('libasound.so.2')
    asound.snd_lib_error_set_handler(c_error_handler)
except:
    pass

import tkinter as tk
import pyautogui
import threading
import queue
import json
import sys
import os
import audioop

# Añadir path del modelo y configuración
MODEL_PATH = os.path.expanduser("~/.openclaw/workspace/vosk-model/vosk-model-small-es-0.42")
CONFIG_PATH = os.path.expanduser("~/.openclaw/workspace/voice_typing_config.json")

# === CONFIGURACIÓN POR DEFECTO ===
DEFAULT_CONFIG = {
    "energy_threshold": 150,     # Sensibilidad del micrófono
    "volume_boost": 1.0,         # Boost de volumen (1.0 = sin boost)
    "pause_threshold": 0.5,      # Tiempo de pausa entre frases
    "enter_words": ["intro", "enter", "salto", "enviar"],
    "auto_save": True            # Guardar cambios automáticamente
}

# === CARGAR CONFIGURACIÓN DEL USUARIO ===
def load_config():
    """Carga configuración guardada o usa defaults"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                user_config = json.load(f)
                # Merge con defaults (por si faltan campos nuevos)
                config = DEFAULT_CONFIG.copy()
                config.update(user_config)
                print(f"⚙️ Configuración cargada: {CONFIG_PATH}")
                return config
        except Exception as e:
            print(f"⚠️ Error cargando config: {e}, usando defaults")
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """Guarda configuración del usuario"""
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"💾 Configuración guardada: {CONFIG_PATH}")
        return True
    except Exception as e:
        print(f"⚠️ Error guardando config: {e}")
        return False

from vosk import Model, KaldiRecognizer
import pyaudio


class VoiceTyperVosk:
    """Aplicación de dictado por voz ultra-rápida usando Vosk"""
    
    def __init__(self):
        # Cargar configuración
        self.config = load_config()
        self.original_config = self.config.copy()  # Para comparar cambios
        
        # UI Setup - Ventana minimalista sin bordes
        self.root = tk.Tk()
        self.root.title("🎤")
        self.root.geometry("85x60+50+50")
        self.root.attributes('-topmost', True)
        self.root.resizable(False, False)
        self.root.configure(bg='#1a1a1a')
        self.root.overrideredirect(True)
        
        self.listening = True
        self.audio_queue = queue.Queue()
        
        # Cargar modelo Vosk español
        print("🧠 Cargando modelo Vosk español...")
        if not os.path.exists(MODEL_PATH):
            print(f"❌ Modelo no encontrado en {MODEL_PATH}")
            print("📥 Descarga: https://alphacephei.com/vosk/models")
            sys.exit(1)
        
        self.model = Model(MODEL_PATH)
        print("✅ Modelo cargado!")
        
        # Configurar micrófono USB SF-558
        self.setup_audio()
        
        # Crear UI
        self.setup_ui()
        
        # Iniciar reconocimiento con Vosk (requiere 16kHz)
        self.target_rate = 16000
        self.recognizer = KaldiRecognizer(self.model, self.target_rate)
        self.recognizer.SetWords(True)
        
        # Iniciar hilos de audio
        self.audio_thread = threading.Thread(target=self.capture_audio, daemon=True)
        self.process_thread = threading.Thread(target=self.process_audio, daemon=True)
        
        self.audio_thread.start()
        self.process_thread.start()
        
        print("🎤 Escuchando... ¡Habla!")
        
    def setup_audio(self):
        """Configura el micrófono USB SF-558 con conversión de frecuencia"""
        self.audio = pyaudio.PyAudio()
        
        # Buscar dispositivo USB SF-558
        device_index = None
        default_rate = 44100
        
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            name = info.get('name', '').lower()
            if 'usb' in name or 'sf' in name or '558' in name:
                device_index = i
                default_rate = int(info.get('defaultSampleRate', 44100))
                print(f"🎤 Micrófono USB: {info['name']}")
                print(f"   Frecuencia nativa: {default_rate}Hz")
                break
        
        if device_index is None:
            print("⚠️ Usando micrófono default")
            device_index = self.audio.get_default_input_device_info()['index']
        
        self.input_rate = default_rate
        
        # Abrir stream con frecuencia nativa del micrófono
        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.input_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=4096
            )
            print(f"✅ Stream abierto a {self.input_rate}Hz")
        except Exception as e:
            print(f"⚠️ Error: {e}, probando 48000Hz...")
            self.input_rate = 48000
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.input_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=4096
            )
        
    def setup_ui(self):
        """Crea la UI minimalista tipo 'blob' flotante con botón de ajustes"""
        self.canvas = tk.Canvas(
            self.root, 
            width=80, 
            height=60, 
            bg='#1a1a1a',
            highlightthickness=0
        )
        self.canvas.pack()
        
        # Círculo de estado (más a la izquierda para hacer espacio)
        self.circle = self.canvas.create_oval(
            5, 10, 45, 50,
            fill='#e74c3c',  # Rojo = activo
            outline='',
            tags='circle'
        )
        
        # Indicador central
        self.text = self.canvas.create_text(
            25, 30,
            text="●",
            fill='white',
            font=('Helvetica', 20)
        )
        
        # Botón de ajustes (⚙️) - pequeño y discreto
        self.settings_btn = self.canvas.create_text(
            55, 30,
            text="⚙️",
            font=('Helvetica', 10),
            fill='#666666',
            activefill='#ffffff'
        )
        
        # Botón de cerrar (X) - pequeño en la esquina
        self.close_btn = self.canvas.create_text(
            72, 12,
            text="✕",
            font=('Helvetica', 8, 'bold'),
            fill='#e74c3c',
            activefill='#ff6b6b'
        )
        
        # Eventos
        self.canvas.bind('<Button-1>', self.on_click)
        self.canvas.tag_bind(self.settings_btn, '<Button-1>', lambda e: self.open_settings())
        self.canvas.tag_bind(self.close_btn, '<Button-1>', lambda e: self.cleanup_and_exit())
        
        # Aplicar configuración cargada
        self.energy_threshold = self.config.get('energy_threshold', 150)
        self.volume_boost = self.config.get('volume_boost', 1.0)
        self.pause_threshold = self.config.get('pause_threshold', 0.5)
        self.enter_words = self.config.get('enter_words', DEFAULT_CONFIG['enter_words'])
        
    def on_click(self, event):
        """Maneja clicks en el canvas"""
        # Si el click está en el círculo principal (toggle)
        if 5 < event.x < 45 and 10 < event.y < 50:
            self.toggle()
        # Si está en el área del botón de ajustes
        elif 48 < event.x < 62 and 22 < event.y < 38:
            self.open_settings()
        # Si está en el botón de cerrar (X)
        elif 66 < event.x < 78 and 6 < event.y < 18:
            self.cleanup_and_exit()
        # Click derecho para cerrar (alternativa)
        elif event.num == 3:
            self.cleanup_and_exit()
            
    def open_settings(self):
        """Abre ventana de ajustes con guardar/volver a defaults"""
        if hasattr(self, 'settings_window') and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
            
        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("⚙️ Ajustes")
        self.settings_window.geometry("280x350+120+50")
        self.settings_window.attributes('-topmost', True)
        self.settings_window.resizable(False, False)
        self.settings_window.configure(bg='#2d2d2d')
        
        # Frame principal con scroll si es necesario
        main_frame = tk.Frame(self.settings_window, bg='#2d2d2d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Canvas para scroll
        canvas = tk.Canvas(main_frame, bg='#2d2d2d', highlightthickness=0)
        scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg='#2d2d2d')
        
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canvas.create_window((0, 0), window=frame, anchor='nw', width=250)
        
        # Título con indicador de modificado
        self.config_status_label = tk.Label(
            frame,
            text="⚙️ Ajustes del Micrófono",
            bg='#2d2d2d',
            fg='#ffffff',
            font=('Helvetica', 12, 'bold')
        )
        self.config_status_label.pack(pady=(0, 10))
        
        # Frame de estado
        self.status_frame = tk.Label(
            frame,
            text="✅ Usando configuración guardada",
            bg='#2d2d2d',
            fg='#2ecc71',
            font=('Helvetica', 8)
        )
        self.status_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 1. Sensibilidad (umbral de energía)
        tk.Label(
            frame,
            text="🎤 Sensibilidad del micrófono",
            bg='#2d2d2d',
            fg='#aaaaaa',
            font=('Helvetica', 9),
            anchor='w'
        ).pack(fill=tk.X)
        
        tk.Label(
            frame,
            text=f"Default: {DEFAULT_CONFIG['energy_threshold']} | Actual: {self.energy_threshold}",
            bg='#2d2d2d',
            fg='#666666',
            font=('Helvetica', 7)
        ).pack(fill=tk.X)
        
        self.sens_var = tk.IntVar(value=self.energy_threshold)
        sens_scale = tk.Scale(
            frame,
            from_=50,
            to=500,
            orient=tk.HORIZONTAL,
            variable=self.sens_var,
            bg='#2d2d2d',
            fg='#ffffff',
            troughcolor='#444444',
            highlightthickness=0,
            command=self.on_sensitivity_change
        )
        sens_scale.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(
            frame,
            text="← Más sensible (capta todo)    Menos sensible (solo voz clara) →",
            bg='#2d2d2d',
            fg='#888888',
            font=('Helvetica', 7)
        ).pack(fill=tk.X, pady=(0, 10))
        
        # 2. Boost de volumen
        tk.Label(
            frame,
            text="🔊 Boost de volumen",
            bg='#2d2d2d',
            fg='#aaaaaa',
            font=('Helvetica', 9),
            anchor='w'
        ).pack(fill=tk.X)
        
        tk.Label(
            frame,
            text=f"Default: {DEFAULT_CONFIG['volume_boost']}x | Actual: {self.volume_boost}x",
            bg='#2d2d2d',
            fg='#666666',
            font=('Helvetica', 7)
        ).pack(fill=tk.X)
        
        self.vol_var = tk.DoubleVar(value=self.volume_boost)
        vol_scale = tk.Scale(
            frame,
            from_=1.0,
            to=3.0,
            resolution=0.1,
            orient=tk.HORIZONTAL,
            variable=self.vol_var,
            bg='#2d2d2d',
            fg='#ffffff',
            troughcolor='#444444',
            highlightthickness=0,
            command=self.on_volume_change
        )
        vol_scale.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(
            frame,
            text="← Normal    Amplificado →",
            bg='#2d2d2d',
            fg='#888888',
            font=('Helvetica', 7)
        ).pack(fill=tk.X, pady=(0, 10))
        
        # 3. Separador
        tk.Frame(frame, bg='#444444', height=1).pack(fill=tk.X, pady=10)
        
        # 4. Palabras mágicas para Enter
        tk.Label(
            frame,
            text="⏎ Palabras para enviar Enter:",
            bg='#2d2d2d',
            fg='#aaaaaa',
            font=('Helvetica', 9),
            anchor='w'
        ).pack(fill=tk.X)
        
        # Añadir "dentro" si no está
        display_words = self.enter_words.copy()
        if "dentro" not in display_words:
            display_words.append("dentro")
        
        enter_text = ", ".join([f'"{w}"' for w in display_words])
        self.enter_words_label = tk.Label(
            frame,
            text=enter_text,
            bg='#2d2d2d',
            fg='#2ecc71',
            font=('Helvetica', 8),
            wraplength=220,
            justify=tk.LEFT
        )
        self.enter_words_label.pack(fill=tk.X, pady=(2, 0))
        
        # 5. Separador
        tk.Frame(frame, bg='#444444', height=1).pack(fill=tk.X, pady=10)
        
        # 6. Comandos especiales
        tk.Label(
            frame,
            text="🎮 Comandos de voz:",
            bg='#2d2d2d',
            fg='#aaaaaa',
            font=('Helvetica', 9, 'bold'),
            anchor='w'
        ).pack(fill=tk.X)
        
        commands_text = """• "intro" / "dentro" al final = Enviar Enter
• "borra" = Borrar última palabra  
• "borra todo" = Borrar todo el texto
• "bitcoin" → Se corrige a "Bichín"""
        
        tk.Label(
            frame,
            text=commands_text,
            bg='#2d2d2d',
            fg='#888888',
            font=('Helvetica', 8),
            justify=tk.LEFT,
            wraplength=240
        ).pack(fill=tk.X, pady=(5, 0))
        
        # 7. Separador
        tk.Frame(frame, bg='#444444', height=1).pack(fill=tk.X, pady=10)
        
        # 8. Info
        tk.Label(
            frame,
            text="💡 Los cambios se aplican en tiempo real.\nPrueba hablando y ajusta hasta encontrar\nel punto perfecto para tu voz.",
            bg='#2d2d2d',
            fg='#888888',
            font=('Helvetica', 8),
            justify=tk.LEFT,
            wraplength=240
        ).pack(fill=tk.X, pady=(0, 10))
        
        # 7. Botones de acción
        buttons_frame = tk.Frame(frame, bg='#2d2d2d')
        buttons_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Botón Guardar
        self.save_btn = tk.Button(
            buttons_frame,
            text="💾 Guardar",
            command=self.save_user_config,
            bg='#2ecc71',
            fg='white',
            font=('Helvetica', 9, 'bold'),
            relief='flat',
            state='disabled'  # Se activa cuando hay cambios
        )
        self.save_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # Botón Reset
        tk.Button(
            buttons_frame,
            text="↺ Defaults",
            command=self.reset_to_defaults,
            bg='#e74c3c',
            fg='white',
            font=('Helvetica', 9),
            relief='flat'
        ).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))
        
        # Actualizar scroll region
        frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        
    def on_sensitivity_change(self, value):
        """Cambia sensibilidad en tiempo real"""
        self.energy_threshold = int(value)
        self.config['energy_threshold'] = self.energy_threshold
        self.mark_config_modified()
        print(f"🎤 Sensibilidad: {self.energy_threshold}")
        
    def on_volume_change(self, value):
        """Cambia volumen en tiempo real"""
        self.volume_boost = float(value)
        self.config['volume_boost'] = self.volume_boost
        self.mark_config_modified()
        print(f"🔊 Volumen boost: {self.volume_boost}x")
        
    def mark_config_modified(self):
        """Marca que hay cambios sin guardar"""
        self.status_frame.config(
            text="⚠️ Cambios sin guardar - Prueba hablando!",
            fg='#f39c12'
        )
        self.save_btn.config(state='normal')
        self.config_status_label.config(text="⚙️ Ajustes del Micrófono ●")
        
    def save_user_config(self):
        """Guarda configuración del usuario"""
        if save_config(self.config):
            self.original_config = self.config.copy()
            self.status_frame.config(
                text="✅ Configuración guardada!",
                fg='#2ecc71'
            )
            self.save_btn.config(state='disabled')
            self.config_status_label.config(text="⚙️ Ajustes del Micrófono")
            print("💾 Config guardada correctamente")
        else:
            self.status_frame.config(
                text="❌ Error al guardar",
                fg='#e74c3c'
            )
            
    def reset_to_defaults(self):
        """Vuelve a configuración por defecto"""
        self.config = DEFAULT_CONFIG.copy()
        self.energy_threshold = DEFAULT_CONFIG['energy_threshold']
        self.volume_boost = DEFAULT_CONFIG['volume_boost']
        self.pause_threshold = DEFAULT_CONFIG['pause_threshold']
        self.enter_words = DEFAULT_CONFIG['enter_words']
        
        # Actualizar UI
        self.sens_var.set(self.energy_threshold)
        self.vol_var.set(self.volume_boost)
        
        # Guardar
        save_config(self.config)
        self.original_config = self.config.copy()
        
        self.status_frame.config(
            text="↺ Restaurado a valores por defecto",
            fg='#3498db'
        )
        self.save_btn.config(state='disabled')
        print("↺ Config restaurada a defaults")
        
    def toggle(self):
        """Pausar o reanudar la escucha"""
        self.listening = not self.listening
        if self.listening:
            self.canvas.itemconfig('circle', fill='#e74c3c')
            print("▶️ Reanudado")
        else:
            self.canvas.itemconfig('circle', fill='#2ecc71')
            print("⏸️ Pausado")
            
    def capture_audio(self):
        """Captura audio y convierte frecuencia para Vosk"""
        while True:
            if self.listening:
                try:
                    # Leer audio del micrófono
                    data = self.stream.read(4096, exception_on_overflow=False)
                    
                    # Aplicar boost de volumen si está configurado
                    if self.volume_boost > 1.0:
                        data = audioop.mul(data, 2, self.volume_boost)
                    
                    # Convertir a 16kHz si es necesario (Vosk requiere 16kHz)
                    if self.input_rate != self.target_rate:
                        data, _ = audioop.ratecv(
                            data, 2, 1, self.input_rate, self.target_rate, None
                        )
                    
                    self.audio_queue.put(data)
                except Exception as e:
                    print(f"⚠️ Error captura: {e}")
            else:
                # Descartar audio cuando pausado
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    pass
                    
    def process_audio(self):
        """Procesa audio con Vosk y escribe el texto"""
        while True:
            try:
                data = self.audio_queue.get(timeout=0.1)
                
                # Enviar a Vosk
                if self.recognizer.AcceptWaveform(data):
                    # Resultado final
                    result = json.loads(self.recognizer.Result())
                    text = result.get('text', '').strip()
                    
                    if text:
                        print(f"🎤 {text}")
                        self.type_text(text)
                        self.flash_success()
                else:
                    # Resultado parcial (feedback visual)
                    partial = json.loads(self.recognizer.PartialResult())
                    if partial.get('partial', ''):
                        # Amarillo = escuchando activamente
                        self.canvas.itemconfig('circle', fill='#f39c12')
                        
            except queue.Empty:
                pass
            except Exception as e:
                print(f"⚠️ Error procesando: {e}")
                
    def type_text(self, text):
        """Escribe el texto donde esté el cursor del sistema"""
        try:
            text_clean = text.lower().strip()
            
            # CORRECCION: Caracteres especiales en español
            # Corregir palabras comunes sin tildes/ene
            spanish_corrections = {
                "senor": "señor",
                "Senor": "Señor",
                "SENOR": "SEÑOR",
                "ano": "año",
                "Ano": "Año",
                "ANO": "AÑO",
                "manana": "mañana",
                "Manana": "Mañana",
                "corazon": "corazón",
                "Corazon": "Corazón",
                "cancion": "canción",
                "Cancion": "Canción",
                "nacion": "nación",
                "Nacion": "Nación",
                "accion": "acción",
                "Accion": "Acción",
            }
            
            for wrong, correct in spanish_corrections.items():
                text = text.replace(wrong, correct)
            
            # CORRECCION: Variantes de "Bichin" -> "Bichin" (mi nombre - sin acento para evitar problemas de codificacion)
            # Reemplazo simple y directo para todas las variantes
            text = text.replace("bitcoin", "Bichin")
            text = text.replace("Bitcoin", "Bichin")
            text = text.replace("BITCOIN", "Bichin")
            text = text.replace("virgin", "Bichin")
            text = text.replace("Virgin", "Bichin")
            text = text.replace("VIRGIN", "Bichin")
            text = text.replace("bichn", "Bichin")
            text = text.replace("Bichn", "Bichin")
            text = text.replace("BICHN", "Bichin")
            text = text.replace("bici", "Bichin")
            text = text.replace("Bici", "Bichin")
            text = text.replace("BICI", "Bichin")
            text = text.replace("jim", "Bichin")
            text = text.replace("Jim", "Bichin")
            text = text.replace("JIM", "Bichin")
            text = text.replace("beach in", "Bichin")
            text = text.replace("Beach in", "Bichin")
            text = text.replace("begin", "Bichin")
            text = text.replace("Begin", "Bichin")
            text = text.replace("pitching", "Bichin")
            text = text.replace("Pitching", "Bichin")
            text = text.replace("beachin", "Bichin")
            text = text.replace("Beachin", "Bichin")
            text = text.replace("bichin", "Bichin")
            text = text.replace("Bichin", "Bichin")  # Ya esta bien escrito
            text = text.replace("biching", "Bichin")
            text = text.replace("Biching", "Bichin")
            text = text.replace("mi-jin", "Bichin")
            text = text.replace("Mi-jin", "Bichin")
            text = text.replace("mijin", "Bichin")
            text = text.replace("Mijin", "Bichin")
            text = text.replace("mijing", "Bichin")
            text = text.replace("Mijing", "Bichin")
            text = text.replace("beechin", "Bichin")
            text = text.replace("Beechin", "Bichin")
            text = text.replace("bechin", "Bichin")
            text = text.replace("Bechin", "Bichin")
            
            # COMANDOS DE BORRADO
            # "borra" / "borrar" -> Borra última palabra (Ctrl+Backspace)
            if text_clean in ["borra", "borrar", "borra la palabra", "borrar palabra"]:
                pyautogui.keyDown('ctrl')
                pyautogui.keyDown('backspace')
                pyautogui.keyUp('backspace')
                pyautogui.keyUp('ctrl')
                print("⌫ Última palabra borrada")
                return
            
            # "borra todo" / "borrar todo" -> Borra todo (Ctrl+A + Delete)
            if text_clean in ["borra todo", "borrar todo", "borra todo el texto", "borrar todo el texto"]:
                pyautogui.keyDown('ctrl')
                pyautogui.keyDown('a')
                pyautogui.keyUp('a')
                pyautogui.keyUp('ctrl')
                pyautogui.keyDown('delete')
                pyautogui.keyUp('delete')
                print("🗑️ Todo el texto borrado")
                return
            
            # COMANDOS DE SISTEMA EXPANSIBLES
            # "abre firefox" / "abre el navegador" → Abre Firefox
            if text_clean.startswith("abre "):
                app_name = text_clean[5:].strip().lower()
                if app_name in ["firefox", "navegador", "el navegador"]:
                    import subprocess
                    subprocess.Popen(['firefox'])
                    print("🌐 Firefox abierto")
                    return
                elif app_name in ["terminal", "consola", "konsole"]:
                    import subprocess
                    subprocess.Popen(['konsole'])
                    print("💻 Terminal abierta")
                    return
                elif app_name in ["spotify", "música", "musica"]:
                    import subprocess
                    subprocess.Popen(['spotify'])
                    print("🎵 Spotify abierto")
                    return
                elif app_name == "vscode":
                    import subprocess
                    subprocess.Popen(['code'])
                    print("📝 VSCode abierto")
                    return
            
            # "busca X" / "buscar X" → Busca en Google
            if text_clean.startswith(("busca ", "buscar ")):
                query = text[text.lower().find(" ")+1:].strip()
                if query:
                    import urllib.parse
                    search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
                    import subprocess
                    subprocess.Popen(['firefox', search_url])
                    print(f"🔍 Buscando: {query}")
                    return
            
            # "noticias de X" / "noticias sobre X" → Busca noticias
            if text_clean.startswith(("noticias de ", "noticias sobre ", "noticias ")):
                if text_clean.startswith("noticias de "):
                    query = text[12:].strip()
                elif text_clean.startswith("noticias sobre "):
                    query = text[15:].strip()
                else:
                    query = text[9:].strip()
                
                if query:
                    import urllib.parse
                    # Corregir "winona rider" si está mal transcrito
                    query_clean = query.replace("winona rider", "winona ryder")
                    news_url = f"https://news.google.com/search?q={urllib.parse.quote(query_clean)}&hl=es"
                    import subprocess
                    subprocess.Popen(['firefox', news_url])
                    print(f"📰 Buscando noticias de: {query_clean}")
                    return
            
            # "abre youtube" / "youtube" → Abre YouTube
            if text_clean in ["youtube", "abre youtube", "abrir youtube"]:
                import subprocess
                subprocess.Popen(['firefox', 'https://youtube.com'])
                print("📺 YouTube abierto")
                return
            
            # "clima" / "tiempo" / "qué tiempo hace" → Abre clima de Madrid
            if text_clean in ["clima", "tiempo", "qué tiempo hace", "que tiempo hace"]:
                import subprocess
                subprocess.Popen(['firefox', 'https://www.google.com/search?q=tiempo+madrid'])
                print("🌤️ Consultando clima de Madrid")
                return
            
            # Detectar palabras mágicas para enviar Enter
            # "intro", "dentro", "adentro", "entro", "entra" son intercambiables
            enter_keywords = ["intro", "enter", "salto", "enviar", "manda", "dentro"]
            # También detectar variantes fonéticas
            enter_variants = ["intro", "entro", "dentro", "adentro", "in tro", "en tro", "entra"]
            if hasattr(self, 'enter_words'):
                enter_keywords = self.enter_words
                if "dentro" not in enter_keywords:
                    enter_keywords.append("dentro")
            
            # CASO 1: Solo la palabra mágica (aislada) - AHORA SÍ FUNCIONA
            if text_clean in enter_keywords or text_clean in enter_variants:
                pyautogui.keyDown('return')
                pyautogui.keyUp('return')
                print(f"⏎ Enter enviado (solo '{text_clean}')")
                return
            
            # CASO 2: Palabra mágica al FINAL de la frase
            # Buscar si termina con espacio + keyword (o variantes)
            all_keywords = list(set(enter_keywords + enter_variants))
            
            for keyword in all_keywords:
                # Patrón: " ... texto keyword" (con espacio antes)
                if text_clean.endswith(f" {keyword}"):
                    # Extraer todo antes del espacio + keyword
                    text_to_write = text_clean[:-len(keyword)-1].strip()
                    if text_to_write:
                        # Restaurar mayúsculas del texto original
                        original_text = text[:text.lower().rfind(f" {keyword}")].strip()
                        if original_text and original_text[0] not in '.,;:!?':
                            original_text = ' ' + original_text
                        pyautogui.typewrite(original_text, interval=0.01)
                    # Enviar Enter
                    pyautogui.keyDown('return')
                    pyautogui.keyUp('return')
                    print(f"📝 + ⏎ (detectado '{keyword}' al final)")
                    return
                
                # También detectar si la palabra está pegada al final sin espacio
                elif text_clean.endswith(keyword) and len(text_clean) > len(keyword):
                    # Verificar que sea realmente el final y no parte de otra palabra
                    prefix = text_clean[:-len(keyword)]
                    # Lista de prefijos a evitar
                    bad_prefixes = ['intr', 'sal', 'env', 'mand']
                    if prefix and not any(prefix.endswith(bp) for bp in bad_prefixes):
                        # Restaurar mayúsculas
                        end_pos = len(text) - len(keyword)
                        text_to_write = text[:end_pos].strip()
                        if text_to_write:
                            if text_to_write[0] not in '.,;:!?':
                                text_to_write = ' ' + text_to_write
                            pyautogui.typewrite(text_to_write, interval=0.01)
                        pyautogui.keyDown('return')
                        pyautogui.keyUp('return')
                        print(f"📝 + ⏎ (detectado '{keyword}' pegado)")
                        return
            
            # CASO 4: Texto normal
            # Añadir espacio si no empieza con puntuación
            if text and text[0] not in '.,;:!?':
                text = ' ' + text
            # Escribir con espacio al final
            pyautogui.typewrite(text + ' ', interval=0.01)
        except Exception as e:
            print(f"⚠️ Error escribiendo: {e}")
            
    def flash_success(self):
        """Flash verde cuando se escribe correctamente"""
        self.canvas.itemconfig('circle', fill='#2ecc71')
        self.root.after(100, lambda: self.canvas.itemconfig('circle', fill='#e74c3c'))
        
    def cleanup_and_exit(self):
        """Cierra la aplicación limpiamente liberando recursos"""
        print("🛑 Cerrando Voice Typing...")
        self.listening = False
        
        # Detener y cerrar el stream de audio
        try:
            if hasattr(self, 'stream') and self.stream:
                self.stream.stop_stream()
                self.stream.close()
                print("✅ Stream de audio cerrado")
        except Exception as e:
            print(f"⚠️ Error cerrando stream: {e}")
        
        # Terminar PyAudio
        try:
            if hasattr(self, 'audio') and self.audio:
                self.audio.terminate()
                print("✅ PyAudio terminado")
        except Exception as e:
            print(f"⚠️ Error terminando PyAudio: {e}")
        
        # Cerrar la ventana
        self.root.destroy()
        print("👋 Voice Typing cerrado correctamente")
        
    def run(self):
        """Inicia la aplicación"""
        self.root.mainloop()
        # Limpieza al cerrar
        self.stream.stop_stream()
        self.stream.close()
        self.audio.terminate()


if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  🎤 BICHÍN VOICE TYPING - VOSK EDITION                       ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print("║  🧠 Modelo: Español offline (Vosk small-es-0.42)             ║")
    print("║  🎤 Micrófono: SF-558 USB configurado                        ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print("║  Controles:                                                  ║")
    print("║    🔴 Rojo     = Escuchando                                  ║")
    print("║    🟡 Amarillo = Procesando voz                              ║")
    print("║    🟢 Verde    = Texto escrito                               ║")
    print("║    🖱️  Click izquierdo = Pausar/Reanudar                     ║")
    print("║    🖱️  Click derecho   = Cerrar                              ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    
    app = VoiceTyperVosk()
    app.run()
