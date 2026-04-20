"""
email_service.py — Modul pengiriman struk via SMTP
Mengirim email HTML secara asynchronous.
"""
import os
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

# Konfigurasi SMTP
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

LOG_FILE = "system_logs.txt"

def _write_log(message):
    """Tulis pesan log ke file dengan timestamp"""
    from datetime import datetime
    tgl = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{tgl}] {message}\n")
    except:
        pass

def _send_email_async(to_email, subject, html_content):
    """Logika inti pengiriman email (internal)"""
    if not EMAIL_USER or not EMAIL_PASSWORD or not to_email:
        _write_log(f"FAILED: Konfigurasi email tidak lengkap atau recipient kosong. (User: {EMAIL_USER})")
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = f"Hubb Shoestreatment <{EMAIL_USER}>"
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(html_content, 'html'))

        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
        _write_log(f"SUCCESS: Email berhasil dikirim ke {to_email}")
    except Exception as e:
        _write_log(f"ERROR: Gagal kirim ke {to_email}. Detail: {str(e)}")

def kirim_struk(email, trx_id, customer, layanan, total, tanggal_str, catatan=""):
    """
    Kirim struk email secara asynchronous agar tidak memicu delay di UI Streamlit.
    """
    if not email or "@" not in email:
        _write_log(f"SKIP: Email tidak valid '{email}' untuk Order #{trx_id}")
        return
        
    _write_log(f"QUEUED: Memproses struk #{trx_id} untuk {email}")
        
    subject = f"Struk Pembayaran #{trx_id:05d} — Hubb Shoestreatment"
    
    # Nilai rupiah format manual untuk email
    total_fmt = f"{int(total):,}".replace(",", ".")
    
    html = f"""
    <html>
    <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 500px; margin: auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
            <div style="background: #1D9E75; color: white; padding: 30px; text-align: center;">
                <h1 style="margin: 0; font-size: 24px;">Hubb Shoestreatment</h1>
                <p style="margin: 5px 0 0; opacity: 0.8;">Struk Pembayaran Digital</p>
            </div>
            
            <div style="padding: 30px;">
                <div style="text-align: center; margin-bottom: 25px;">
                    <div style="font-size: 14px; color: #888;">Nomor Order</div>
                    <div style="font-size: 20px; font-weight: bold; color: #333;">#{trx_id:05d}</div>
                </div>
                
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="border-bottom: 1px solid #eee;">
                        <td style="padding: 10px 0; color: #888;">Customer</td>
                        <td style="padding: 10px 0; text-align: right; font-weight: 500;">{customer}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #eee;">
                        <td style="padding: 10px 0; color: #888;">Layanan</td>
                        <td style="padding: 10px 0; text-align: right; font-weight: 500;">{layanan}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #eee;">
                        <td style="padding: 10px 0; color: #888;">Tanggal</td>
                        <td style="padding: 10px 0; text-align: right; font-weight: 500;">{tanggal_str}</td>
                    </tr>
                </table>
                
                <div style="margin-top: 30px; padding: 20px; background: #f8fdfb; border-radius: 8px; border: 1px solid #e1f5ef; text-align: center;">
                    <div style="font-size: 14px; color: #1D9E75; font-weight: 600;">TOTAL PEMBAYARAN</div>
                    <div style="font-size: 28px; font-weight: 800; color: #1D9E75; margin-top: 5px;">Rp {total_fmt}</div>
                </div>
                
                {f'<div style="margin-top: 20px; font-size: 13px; color: #666; font-style: italic;"><b>Catatan:</b> {catatan}</div>' if catatan else ''}
                
                <div style="margin-top: 40px; text-align: center; font-size: 12px; color: #aaa;">
                    Terima kasih telah mempercayakan sepatu Anda kepada kami!<br>
                    Barang yang sudah diambil tidak dapat dikembalikan.
                </div>
            </div>
            
            <div style="background: #f9f9f9; padding: 15px; text-align: center; font-size: 11px; color: #bbb; border-top: 1px solid #eee;">
                &copy; 2026 Hubb Shoestreatment — Cloud ERP System
            </div>
        </div>
    </body>
    </html>
    """
    
    # Jalankan pengiriman di background thread agar Streamlit tidak lag
    thread = threading.Thread(target=_send_email_async, args=(email, subject, html))
    thread.start()
