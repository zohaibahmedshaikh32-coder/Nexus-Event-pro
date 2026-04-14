from flask import Flask, render_template, request
import mysql.connector

app = Flask(__name__)
app.secret_key = "nexus_2026_final"

# ONE function to rule them all
# UPDATE THIS SECTION
def get_db():
    return mysql.connector.connect(
        host="localhost", 
        user="root", 
        password="password", # <--- CHANGE THIS to your working password
        database="event_management",
        port=3306 # Laragon uses 3306
    )

@app.route('/')
def home():
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM venue")
        venues = cursor.fetchall()
        cursor.execute("SELECT * FROM package")
        packages = cursor.fetchall()
        db.close()
        return render_template('index.html', venues=venues, packages=packages)
    except Exception as e:
        return f"Database Connection Error: {e}. Make sure MySQL is running!"

@app.route('/register', methods=['POST'])
def register():
    u_name = request.form.get('reg_name')
    u_phone = request.form.get('reg_phone')
    u_email = request.form.get('reg_email')
    u_cnic = request.form.get('reg_cnic')
    
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT Client_ID FROM client WHERE Phone=%s OR CNIC=%s", (u_phone, u_cnic))
        existing = cursor.fetchone()
        
        if existing:
            cid = existing[0]
            msg = "You are already registered!"
        else:
            cursor.execute("INSERT INTO client (Name, Phone, Email, CNIC) VALUES (%s, %s, %s, %s)", 
                           (u_name, u_phone, u_email, u_cnic))
            db.commit()
            cid = cursor.lastrowid
            msg = "Registration Successful!"

        return f"""
        <div style="text-align:center; padding:50px; font-family:sans-serif;">
            <h1 style="color:green;">{msg}</h1>
            <p style="font-size:20px;">YOUR CLIENT ID IS:</p>
            <h1 style="font-size:70px; color:red; border:2px solid red; display:inline-block; padding:10px 30px;">{cid}</h1>
            <p>Copy this ID and use it in the booking form below.</p>
            <a href="/" style="text-decoration:none; background:black; color:white; padding:10px 20px; border-radius:5px;">BACK TO HOME</a>
        </div>
        """
    except Exception as e:
        return f"Registration Error: {e}"
    finally:
        db.close()

@app.route('/book', methods=['POST'])
def book():
    form_cid = request.form.get('book_cid') 
    form_vid = request.form.get('book_vid')
    form_pid = request.form.get('book_pid')
    form_etype = request.form.get('book_etype')
    form_date = request.form.get('book_date')

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT Name FROM client WHERE Client_ID = %s", (form_cid,))
        client_record = cursor.fetchone()
        
        if not client_record:
            return f"<h1>ID {form_cid} Not Found!</h1><p>Register first to get an ID.</p><a href='/'>Back</a>"

        cursor.execute("""
            INSERT INTO booking (Client_ID, Event_Type, Venue_ID, Package_ID, Status, Booking_Date) 
            VALUES (%s, %s, %s, %s, 'Pending', %s)
        """, (form_cid, form_etype, form_vid, form_pid, form_date))
        db.commit()
        
        return f"<h1>Booking Confirmed for {client_record[0]}!</h1><p>Status: Pending Approval.</p><a href='/'>Home</a>"
    except Exception as e:
        return f"Booking Error: {e}"
    finally:
        db.close()

@app.route('/track', methods=['POST'])
def track_status():
    cid = request.form.get('track_cid')
    if not cid:
        return "Please enter a Client ID. <a href='/'>Back</a>"
    
    db = None # Initialize to avoid errors in 'finally'
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        
        # We use aliases (b and v) to make the query cleaner
        # Make sure 'Venue_ID' exists in BOTH tables
        query = """
            SELECT b.Booking_ID, v.Venue_Name, b.Booking_Date, b.Status 
            FROM booking b 
            JOIN venue v ON b.Venue_ID = v.Venue_ID 
            WHERE b.Client_ID = %s
        """
        cursor.execute(query, (cid,))
        results = cursor.fetchall()
        
        cursor.close()
        if not results:
            return f"<h3>No bookings found for Client ID: {cid}. <a href='/'>Go back</a></h3>"

        return render_template('status.html', results=results, client_id=cid)

    except Exception as e:
        # This will tell us EXACTLY what is wrong (e.g., 'Unknown column')
        return f"<h3>Tracking Error:</h3><p>{str(e)}</p><a href='/'>Back</a>"
    finally:
        if db:
            db.close()

if __name__ == '__main__':
    app.run(debug=True)