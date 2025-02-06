import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, time
from functools import wraps
import pandas as pd
from io import BytesIO

# Flask uygulaması
app = Flask(__name__)
app.secret_key = 'super_secret_key_123!'

# Admin bilgileri
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Veritabanı bağlantısı
DATABASE = 'spinning.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Veritabanını başlatma ve tablo oluşturma
def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS uyeler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad TEXT NOT NULL,
            soyad TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            sifre_hash TEXT NOT NULL,
            kayit_tarihi DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rezervasyonlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uye_id INTEGER NOT NULL,
            bisiklet_no INTEGER NOT NULL CHECK (bisiklet_no BETWEEN 1 AND 20),
            tarih DATE NOT NULL,
            saat TIME NOT NULL,
            admin_rezervasyon BOOLEAN DEFAULT 0,
            FOREIGN KEY (uye_id) REFERENCES uyeler(id)
        )
    ''')

    conn.commit()
    conn.close()

# Veritabanı dosyasını kontrol etme
def init_db():
    if not os.path.exists(DATABASE):
        create_tables()
        print("Veritabanı oluşturuldu.")
    else:
        print("Veritabanı zaten mevcut.")

# Giriş gerekliliği decorator'ı
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Lütfen önce giriş yapın!', 'danger')
            return redirect(url_for('giris'))
        return f(*args, **kwargs)
    return decorated_function

# Rezervasyon zamanı kontrolü
def is_rezervasyon_acik():
    now = datetime.now()
    if now.weekday() not in [0, 2, 4]:
        return False
    return time(11, 0) <= now.time() <= time(18, 0)

# Ana sayfa
@app.route('/')
def anasayfa():
    return render_template('anasayfa.html')

# Üye kayıt
@app.route('/kayit', methods=['GET', 'POST'])
def kayit():
    if request.method == 'POST':
        ad = request.form['ad']
        soyad = request.form['soyad']
        email = request.form['email']
        sifre = request.form['sifre']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id FROM uyeler WHERE email = ?', (email,))
        if cursor.fetchone():
            flash('Bu e-posta zaten kayıtlı!', 'danger')
            conn.close()
            return redirect(url_for('kayit'))

        sifre_hash = generate_password_hash(sifre, method='pbkdf2:sha256')
        cursor.execute('''
            INSERT INTO uyeler (ad, soyad, email, sifre_hash)
            VALUES (?, ?, ?, ?)
        ''', (ad, soyad, email, sifre_hash))

        conn.commit()
        conn.close()
        flash('Kayıt başarılı! Lütfen giriş yapın.', 'success')
        return redirect(url_for('giris'))

    return render_template('kayit.html')

# Üye giriş
@app.route('/giris', methods=['GET', 'POST'])
def giris():
    if request.method == 'POST':
        email = request.form['email']
        sifre = request.form['sifre']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM uyeler WHERE email = ?', (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['sifre_hash'], sifre):
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            flash('Başarıyla giriş yaptınız!', 'success')
            return redirect(url_for('profil'))
        else:
            flash('Geçersiz e-posta veya şifre!', 'danger')

    return render_template('giris.html')

# Üye profili
@app.route('/profil')
@login_required
def profil():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT ad, soyad, email FROM uyeler WHERE id = ?', (session['user_id'],))
    user_info = cursor.fetchone()

    cursor.execute('''
        SELECT bisiklet_no, tarih, saat 
        FROM rezervasyonlar 
        WHERE uye_id = ?
        ORDER BY tarih DESC
    ''', (session['user_id'],))
    rezervasyonlar = cursor.fetchall()

    conn.close()
    return render_template('profil.html', 
                         ad=user_info['ad'],
                         soyad=user_info['soyad'],
                         email=user_info['email'],
                         rezervasyonlar=rezervasyonlar)

# Rezervasyon yap
@app.route('/rezervasyon', methods=['GET', 'POST'])
@login_required
def rezervasyon():
    if request.method == 'POST':
        bisiklet_no = int(request.form['bisiklet_no'])
        tarih = request.form['tarih']
        saat = request.form['saat']

        if not is_rezervasyon_acik():
            flash('Rezervasyonlar sadece Pazartesi, Çarşamba, Cuma 11:00-18:00 arası açıktır!', 'danger')
            return redirect(url_for('rezervasyon'))

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id FROM rezervasyonlar 
            WHERE bisiklet_no = ? AND tarih = ? AND saat = ?
        ''', (bisiklet_no, tarih, saat))
        if cursor.fetchone():
            flash('Bu bisiklet zaten rezerve edilmiş!', 'danger')
            conn.close()
            return redirect(url_for('rezervasyon'))

        cursor.execute('''
            INSERT INTO rezervasyonlar (uye_id, bisiklet_no, tarih, saat)
            VALUES (?, ?, ?, ?)
        ''', (session['user_id'], bisiklet_no, tarih, saat))

        conn.commit()
        conn.close()
        flash('Rezervasyon başarıyla alındı!', 'success')
        return redirect(url_for('profil'))

    return render_template('rezervasyon.html')

# Daha fazla rota tanımlamaları devam eder...

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
