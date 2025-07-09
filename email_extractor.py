import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import time

class FastEmailExtractor:
    def __init__(self, root):
        self.root = root
        self.root.title("Hızlı E-posta Çıkarıcı v2.0")
        self.root.geometry("1000x700")
        
        # Değişkenler
        self.df = pd.DataFrame()
        self.running = False
        self.total_tasks = 0
        self.completed_tasks = 0
        
        # Arayüz
        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(padx=20, pady=20, fill="both", expand=True)
        
        # Kontrol Paneli
        control_frame = ttk.LabelFrame(main_frame, text="Kontrol Paneli")
        control_frame.pack(fill="x", pady=10)
        
        ttk.Button(control_frame, text="Excel Yükle", command=self.load_excel).pack(side="left", padx=5)
        self.start_btn = ttk.Button(control_frame, text="Başlat (F9)", command=self.start_extraction)
        self.start_btn.pack(side="left", padx=5)
        ttk.Button(control_frame, text="Durdur (F10)", command=self.stop_extraction).pack(side="left", padx=5)
        ttk.Button(control_frame, text="Excel Kaydet", command=self.save_results).pack(side="right", padx=5)
        
        # İstatistikler
        stats_frame = ttk.Frame(main_frame)
        stats_frame.pack(fill="x", pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(stats_frame, variable=self.progress_var, maximum=100)
        self.progress.pack(fill="x", expand=True)
        
        info_frame = ttk.Frame(stats_frame)
        info_frame.pack(fill="x")
        
        self.status_label = ttk.Label(info_frame, text="Hazır")
        self.status_label.pack(side="left")
        
        self.speed_label = ttk.Label(info_frame, text="0 sites/dk")
        self.speed_label.pack(side="right")
        
        # Sonuç Tablosu
        results_frame = ttk.LabelFrame(main_frame, text="Sonuçlar")
        results_frame.pack(fill="both", expand=True)
        
        columns = ("Website", "Emails", "Status", "Time")
        self.tree = ttk.Treeview(results_frame, columns=columns, show="headings")
        
        # Sütunlar
        self.tree.heading("Website", text="Web Sitesi")
        self.tree.heading("Emails", text="E-postalar")
        self.tree.heading("Status", text="Durum")
        self.tree.heading("Time", text="Süre (sn)")
        
        self.tree.column("Website", width=300)
        self.tree.column("Emails", width=250)
        self.tree.column("Status", width=100)
        self.tree.column("Time", width=80)
        
        scroll_y = ttk.Scrollbar(results_frame, orient="vertical", command=self.tree.yview)
        scroll_y.pack(side="right", fill="y")
        
        scroll_x = ttk.Scrollbar(results_frame, orient="horizontal", command=self.tree.xview)
        scroll_x.pack(side="bottom", fill="x")
        
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self.tree.pack(fill="both", expand=True)
        
        # Klavye Kısayolları
        self.root.bind("<F9>", lambda e: self.start_extraction())
        self.root.bind("<F10>", lambda e: self.stop_extraction())
    
    def load_excel(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx;*.xls")])
        if file_path:
            try:
                self.df = pd.read_excel(file_path)
                self.df['Emails'] = ''
                self.df['Status'] = 'Bekliyor'
                self.df['Time'] = ''
                
                # Tabloyu güncelle
                self.update_table()
                messagebox.showinfo("Başarılı", f"{len(self.df)} web sitesi yüklendi!")
                
            except Exception as e:
                messagebox.showerror("Hata", f"Dosya okunamadı: {str(e)}")
    
    def update_table(self):
        self.tree.delete(*self.tree.get_children())
        for _, row in self.df.iterrows():
            self.tree.insert("", "end", values=(
                row.iloc[0], 
                row['Emails'], 
                row['Status'],
                row['Time']
            ))
    
    def extract_emails(self, url):
        start_time = time.time()
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'http://' + url
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
                'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # E-postaları bul
            emails = set(re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', response.text))
            
            # Mailto linkleri
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                if link['href'].startswith('mailto:'):
                    emails.add(link['href'][7:])
            
            elapsed = round(time.time() - start_time, 2)
            return list(emails), 'Tamamlandı', elapsed
        
        except Exception as e:
            elapsed = round(time.time() - start_time, 2)
            return [], f"Hata: {str(e)}", elapsed
    
    def start_extraction(self):
        if self.running:
            return
        
        if self.df.empty:
            messagebox.showwarning("Uyarı", "Önce Excel dosyası yükleyin")
            return
        
        self.running = True
        self.start_btn.config(state="disabled")
        self.total_tasks = len(self.df)
        self.completed_tasks = 0
        self.start_time = time.time()
        
        # Thread havuzu oluştur
        self.executor = ThreadPoolExecutor(max_workers=15)  # Daha fazla thread
        
        # İşlemleri gönder
        self.futures = []
        for index, row in self.df.iterrows():
            if row['Status'] == 'Bekliyor':
                future = self.executor.submit(self.process_site, index, row.iloc[0])
                self.futures.append(future)
        
        # İlerlemeyi kontrol et
        self.check_progress()
    
    def process_site(self, index, url):
        emails, status, elapsed = self.extract_emails(url)
        
        # DataFrame'i güncelle
        self.df.at[index, 'Emails'] = ', '.join(emails) if emails else 'BULUNMADI'
        self.df.at[index, 'Status'] = status
        self.df.at[index, 'Time'] = elapsed
        
        # GUI güncelleme
        self.root.after(0, self.update_progress)
    
    def check_progress(self):
        if not self.running:
            return
        
        # Hız hesapla
        elapsed_min = (time.time() - self.start_time) / 60
        speed = self.completed_tasks / elapsed_min if elapsed_min > 0 else 0
        self.speed_label.config(text=f"{speed:.1f} sites/dk")
        
        # 100ms sonra tekrar kontrol et
        self.root.after(100, self.check_progress)
    
    def update_progress(self):
        self.completed_tasks += 1
        progress = (self.completed_tasks / self.total_tasks) * 100
        self.progress_var.set(progress)
        self.status_label.config(text=f"İşleniyor: {self.completed_tasks}/{self.total_tasks}")
        
        # Tabloyu güncelle
        self.update_table()
        
        # Tamamlandı mı?
        if self.completed_tasks >= self.total_tasks:
            self.stop_extraction()
            messagebox.showinfo("Tamamlandı", "Tüm işlemler tamamlandı!")
    
    def stop_extraction(self):
        if not self.running:
            return
        
        self.running = False
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)
        self.start_btn.config(state="normal")
        self.status_label.config(text="Durduruldu")
    
    def save_results(self):
        if self.df.empty:
            messagebox.showwarning("Uyarı", "Kaydedilecek veri yok")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")]
        )
        
        if file_path:
            try:
                self.df.to_excel(file_path, index=False)
                messagebox.showinfo("Başarılı", f"Sonuçlar kaydedildi:\n{file_path}")
                os.startfile(file_path)
            except Exception as e:
                messagebox.showerror("Hata", f"Kaydetme başarısız: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = FastEmailExtractor(root)
    root.mainloop()