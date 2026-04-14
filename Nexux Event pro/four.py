import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import mysql.connector
from datetime import date, timedelta
from mysql.connector import pooling
import csv
from tkcalendar import DateEntry
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

# --- Database & Theme Configuration ---
CLR_BG = "#f4f7f6"
CLR_SIDEBAR = "#2c3e50"
CLR_ACCENT = "#3498db"
CLR_SUCCESS = "#27ae60"
CLR_DANGER = "#e74c3c"

# Update line 19 in four.py
conn = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    password="password", # Use your real password here!
    database="event_management"
)

import sqlite3

# --- SQLite Configuration (No XAMPP Needed) ---
# This links to the same file created by your app.py
DB_FILE = "nexus_events.db"

def run_query(q, p=None):
    # This must be inside the function but before the try block
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="password", 
        database="event_management",
        port=3306  # If XAMPP says 3307, change this to 3307
    )
    cur = conn.cursor()
    
    try:
        # 1. Try to execute the SQL
        cur.execute(q, p or ())
        
        if q.strip().upper().startswith("SELECT"):
            res = cur.fetchall()
        else:
            conn.commit()
            res = True
        return res
        
    except mysql.connector.Error as e:
        # 2. Backup plan: What to do if MySQL fails
        print(f"Database Error: {e}")
        return []
        
    finally:
        # 3. Cleanup plan: Always close the connection
        cur.close()
        conn.close()
        
class EventApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Nexus Event Management Pro")
        self.root.geometry("1400x850")
        self.current_model = None
        self.current_input_widgets = []
        self.dropdown_data = {}
        self.search_var = tk.StringVar()
        self.dash_search_var = tk.StringVar()
        
        self.setup_sidebar()
        self.main_container = tk.Frame(self.root, bg=CLR_BG)
        self.main_container.pack(side="right", fill="both", expand=True)
        
        self.top_bar = tk.Frame(self.main_container, bg=CLR_BG, pady=10, padx=20)
        tk.Label(self.top_bar, text="🔍 Search:", bg=CLR_BG).pack(side="left")
        tk.Entry(self.top_bar, textvariable=self.search_var, width=30).pack(side="left", padx=5)
        tk.Button(self.top_bar, text="Search", command=self.perform_search, bg=CLR_ACCENT, fg="white").pack(side="left")
        tk.Button(self.top_bar, text="🔄 Refresh All", command=self.refresh_all, bg=CLR_SUCCESS, fg="white").pack(side="right", padx=5)
        
        self.content_area = tk.Frame(self.main_container, bg=CLR_BG)
        self.content_area.pack(fill="both", expand=True)
        
        self.show_dashboard()

    def setup_sidebar(self):
        sidebar = tk.Frame(self.root, bg=CLR_SIDEBAR, width=220)
        sidebar.pack(side="left", fill="y")
        
        tk.Label(sidebar, text="NEXUS EVENTS", fg="white", bg=CLR_SIDEBAR, 
                 font=("Arial", 16, "bold"), pady=30).pack()
        
        # --- THE UPDATED NAV LIST ---
        nav = [
            ("🏡 Dashboard", self.show_dashboard), 
            ("📅 Availability", self.show_availability), # Add this here!
            ("Clients", "Clients"), 
            ("Venues", "Venues"), 
            ("Packages", "Packages"), 
            ("Bookings", "Bookings"), 
            ("Payments", "Payments"), 
            ("Staff", "Staff")
        ]
        
        for t, target in nav:
            # If the target is a function (like show_dashboard), call it directly.
            # If the target is a string (like "Clients"), use show_view.
            cmd = target if callable(target) else lambda x=target: self.show_view(x)
            
            tk.Button(sidebar, text=t, command=cmd, bg=CLR_SIDEBAR, fg="white", 
                      relief="flat", anchor="w", padx=20, pady=10).pack(fill="x")

    def create_scrolled_tree(self, parent, columns, height=10):
        frame = tk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=height)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        for c in columns:
            tree.heading(c, text=c)
            tree.column(c, width=130, anchor="center")
        return tree

    def approve_booking(self):
        # 1. Check if a row is selected
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selection Required", "Please select a booking to approve!")
            return
        
        # 2. Get the Booking_ID (first column)
        booking_id = self.tree.item(selected[0])['values'][0]
        
        # 3. Ask for confirmation
        if not messagebox.askyesno("Confirm Approval", f"Do you want to confirm Booking ID {booking_id}?"):
            return

        try:
            # 4. Update the Database
            run_query("UPDATE booking SET Status='Confirmed' WHERE Booking_ID=%s", (booking_id,))
            
            # 5. Refresh the UI
            self.refresh_table()
            messagebox.showinfo("Success", f"Booking {booking_id} is now Confirmed!")
        except Exception as e:
            messagebox.showerror("Error", f"Could not approve booking: {e}")
    
    def show_dashboard(self):
        self.top_bar.pack_forget()
        for w in self.content_area.winfo_children(): w.destroy()
        self.fetch_dropdowns()
        
        dash = tk.Frame(self.content_area, bg=CLR_BG, padx=20, pady=20)
        dash.pack(fill="both", expand=True)
        
        # --- Quick Booking ---
        qb = tk.LabelFrame(dash, text="⚡ Quick Booking", bg="white", font=("Arial", 10, "bold"), padx=15, pady=15)
        qb.pack(fill="x", pady=10)
        
        tk.Label(qb, text="Client:", bg="white").grid(row=0, column=0, sticky="w")
        cf = tk.Frame(qb, bg="white")
        cf.grid(row=0, column=1, sticky="w")
        self.q_client = ttk.Combobox(cf, values=[f"{r[0]}-{r[1]}" for r in self.dropdown_data['Client']], width=22)
        self.q_client.pack(side="left")
        tk.Button(cf, text="+", command=self.quick_client_add, bg=CLR_ACCENT, fg="white", font=("Arial", 8, "bold")).pack(side="left", padx=5)

        tk.Label(qb, text="Event Type:", bg="white").grid(row=0, column=2, padx=10)
        self.q_etype = tk.Entry(qb, width=30); self.q_etype.grid(row=0, column=3)

        tk.Label(qb, text="Venue:", bg="white").grid(row=1, column=0, pady=10, sticky="w")
        self.q_venue = ttk.Combobox(qb, values=[f"{r[0]}-{r[1]}" for r in self.dropdown_data['Venue']], width=25)
        self.q_venue.grid(row=1, column=1)

        tk.Label(qb, text="Package:", bg="white").grid(row=1, column=2)
        self.q_pkg = ttk.Combobox(qb, values=[f"{r[0]}-{r[1]}" for r in self.dropdown_data['Package']], width=30)
        self.q_pkg.grid(row=1, column=3)

        tk.Label(qb, text="Date:", bg="white").grid(row=2, column=0, sticky="w")
        self.q_date = DateEntry(qb, width=23, date_pattern='yyyy-mm-dd'); self.q_date.grid(row=2, column=1)

        tk.Button(qb, text="CONFIRM BOOKING", bg=CLR_SUCCESS, fg="white", font=("Arial", 10, "bold"), 
                  command=self.save_quick_booking).grid(row=3, column=0, columnspan=4, pady=15, sticky="ew")

        # --- Recent Bookings & Search ---
        lbl_f = tk.Frame(dash, bg=CLR_BG)
        lbl_f.pack(fill="x", pady=(10,0))
        tk.Label(lbl_f, text="📅 Recent Bookings", font=("Arial", 12, "bold"), bg=CLR_BG).pack(side="left")
        
        # Dashboard Search Bar
        tk.Entry(lbl_f, textvariable=self.dash_search_var, width=25).pack(side="left", padx=20)
        tk.Button(lbl_f, text="🔍 Search Dashboard", command=self.refresh_dash_table, bg=CLR_ACCENT, fg="white", font=("Arial", 8)).pack(side="left")
        
        tk.Button(lbl_f, text="🧾 Generate Selected Receipt", bg="#9b59b6", fg="white", command=lambda: self.preview_receipt(self.dash_tree)).pack(side="right")

        self.dash_tree = self.create_scrolled_tree(dash, ("ID", "Client", "Venue", "Package", "Price", "Date"), height=10)
        self.refresh_dash_table()

    def fetch_dropdowns(self):
        self.dropdown_data['Client'] = run_query("SELECT Client_ID, Name FROM client")
        self.dropdown_data['Venue'] = run_query("SELECT Venue_ID, Venue_Name FROM venue")
        self.dropdown_data['Package'] = run_query("SELECT Package_ID, Package_Name FROM package")
        self.dropdown_data['Booking'] = run_query("SELECT b.Booking_ID, c.Name FROM booking b JOIN client c ON b.Client_ID=c.Client_ID")

    def show_availability(self):
        from datetime import date, timedelta
        import calendar

        self.top_bar.pack_forget()
        for w in self.content_area.winfo_children(): w.destroy()
        
        container = tk.Frame(self.content_area, bg=CLR_BG, padx=30, pady=20)
        container.pack(fill="both", expand=True)

        tk.Label(container, text="Monthly Venue Availability", font=("Arial", 18, "bold"), bg=CLR_BG).pack()

        # Input Row
        top_f = tk.Frame(container, bg=CLR_BG)
        top_f.pack(pady=10)
        
        tk.Label(top_f, text="Select Month/Year:", bg=CLR_BG).pack(side="left", padx=5)
        cal_picker = DateEntry(top_f, width=15, date_pattern='yyyy-mm-dd')
        cal_picker.pack(side="left", padx=5)

        # Scrollable area for the calendar list
        list_frame = tk.Frame(container, bg="white", relief="sunken", bd=1)
        list_frame.pack(fill="both", expand=True, pady=10)
        
        canvas = tk.Canvas(list_frame, bg="white")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable_content = tk.Frame(canvas, bg="white")

        scrollable_content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def show_availability(self):
        from datetime import date, timedelta
        import calendar
        import csv  # Added for CSV export
        from tkinter import filedialog

        self.top_bar.pack_forget()
        for w in self.content_area.winfo_children(): w.destroy()
        
        container = tk.Frame(self.content_area, bg=CLR_BG, padx=30, pady=20)
        container.pack(fill="both", expand=True)

        tk.Label(container, text="Monthly Venue Availability", font=("Arial", 18, "bold"), bg=CLR_BG).pack()

        # --- Control Bar ---
        top_f = tk.Frame(container, bg=CLR_BG)
        top_f.pack(pady=10)
        
        tk.Label(top_f, text="Select Month/Year:", bg=CLR_BG).pack(side="left", padx=5)
        cal_picker = DateEntry(top_f, width=15, date_pattern='yyyy-mm-dd')
        cal_picker.pack(side="left", padx=5)

        self.summary_label = tk.Label(container, text="Load a month to check availability", 
                                     font=("Arial", 11, "bold"), bg="#d5dbdb", pady=8)
        self.summary_label.pack(fill="x", pady=5)

        # --- Scrollable Area ---
        list_frame = tk.Frame(container, bg="white", relief="sunken", bd=1)
        list_frame.pack(fill="both", expand=True, pady=10)
        
        canvas = tk.Canvas(list_frame, bg="white")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable_content = tk.Frame(canvas, bg="white")

        scrollable_content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Internal storage for CSV export
        self.current_report_data = []

        def load_monthly_availability():
            for w in scrollable_content.winfo_children(): w.destroy()
            self.current_report_data = [] # Reset report data
            
            sel_date = cal_picker.get_date()
            year, month = sel_date.year, sel_date.month
            num_days = calendar.monthrange(year, month)[1]

            # --- FIXED LOGIC: Strict String Comparison ---
            # Fetching only the specific month to optimize performance
            query = """SELECT DATE_FORMAT(Booking_Date, '%Y-%m-%d'), Venue_ID 
                       FROM booking 
                       WHERE MONTH(Booking_Date) = %s AND YEAR(Booking_Date) = %s"""
            raw_bookings = run_query(query, (month, year))

            # Build Hash Map
            booking_map = {} 
            if raw_bookings:
                for b_date_str, v_id in raw_bookings:
                    if b_date_str not in booking_map:
                        booking_map[b_date_str] = set()
                    booking_map[b_date_str].add(v_id)

            all_venues = run_query("SELECT Venue_ID, Venue_Name FROM venue")
            venue_total = len(all_venues)
            free_days_count = 0
            full_days_count = 0

            for day in range(1, num_days + 1):
                # Ensure the key format matches SQL: "2026-01-06"
                curr_date_str = f"{year}-{month:02d}-{day:02d}"
                
                booked_ids = booking_map.get(curr_date_str, set())
                free_venues = [v[1] for v in all_venues if v[0] not in booked_ids]

                # Update Counters
                if len(free_venues) == venue_total: free_days_count += 1
                if not free_venues: full_days_count += 1

                # Display Row
                day_f = tk.Frame(scrollable_content, bg="white", pady=3)
                day_f.pack(fill="x", padx=15)
                
                tk.Label(day_f, text=f"{curr_date_str}:", font=("Consolas", 10), bg="white", width=12).pack(side="left")

                status_text = "Available: " + ", ".join(free_venues) if free_venues else "🔴 FULLY BOOKED"
                clr = CLR_SUCCESS if free_venues else CLR_DANGER
                tk.Label(day_f, text=status_text, fg=clr, bg="white").pack(side="left")

                # Store for CSV
                self.current_report_data.append([curr_date_str, status_text])

            self.summary_label.config(text=f"📊 Statistics: {free_days_count} Free | {full_days_count} Full", bg="#ebf5fb")

        def export_to_csv():
            if not self.current_report_data:
                return messagebox.showwarning("Empty", "Please load availability data first!")
            
            path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
            if path:
                with open(path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Date", "Availability Status"])
                    writer.writerows(self.current_report_data)
                messagebox.showinfo("Success", f"Report saved to {path}")

        # --- Buttons ---
        tk.Button(top_f, text="Load Month", command=load_monthly_availability, 
                  bg=CLR_ACCENT, fg="white", font=("Arial", 10, "bold"), padx=15).pack(side="left", padx=5)
        
        tk.Button(top_f, text="📥 Export CSV", command=export_to_csv, 
                  bg=CLR_SUCCESS, fg="white", font=("Arial", 10, "bold"), padx=15).pack(side="left", padx=5)

    def show_view(self, model):
        self.top_bar.pack(side="top", fill="x")
        for w in self.content_area.winfo_children(): w.destroy()
        self.current_model = model
        cols = self.get_cols(model)
        
        view_f = tk.Frame(self.content_area, bg=CLR_BG, padx=20, pady=10)
        view_f.pack(fill="both", expand=True)
        
        self.tree = self.create_scrolled_tree(view_f, cols, height=12)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        
        self.cp = tk.Frame(view_f, bg="white", pady=15, relief="groove", bd=1)
        self.cp.pack(fill="x", pady=10)
        self.current_input_widgets = []
        
        for i, col in enumerate(cols[1:]):
            tk.Label(self.cp, text=col.replace("_", " "), bg="white", font=("Arial", 9, "bold")).grid(row=0, column=i, padx=10, sticky="w")
            if "ID" in col:
                w = ttk.Combobox(self.cp, values=[f"{r[0]}-{r[1]}" for r in self.dropdown_data.get(col.replace("_ID",""), [])], width=18)
                if model == "Payments" and "Booking" in col: w.bind("<<ComboboxSelected>>", self.pay_auto_fill)
            elif "Date" in col or col == "Date" or col == "Booking_Date":
                w = DateEntry(self.cp, width=17, date_pattern='yyyy-mm-dd')
            else:
                w = tk.Entry(self.cp, width=20)
                if model == "Payments" and col == "Paid": w.bind("<KeyRelease>", self.pay_math)
            
            if model == "Payments" and col in ["Total_Price", "Remaining"]: w.config(state="readonly")
            w.grid(row=1, column=i, padx=10, pady=5); self.current_input_widgets.append({'col': col, 'w': w})
        
        btn_f = tk.Frame(self.cp, bg="white")
        btn_f.grid(row=2, column=0, columnspan=len(cols), pady=10)
        
        tk.Button(btn_f, text="➕ Add", command=self.add, bg=CLR_SUCCESS, fg="white", width=10).pack(side="left", padx=5)
        tk.Button(btn_f, text="💾 Update", command=self.edit, bg=CLR_ACCENT, fg="white", width=10).pack(side="left", padx=5)
        
        # --- NEW: APPROVE BUTTON FOR BOOKINGS ---
        if model == "Bookings":
            tk.Button(btn_f, text="✅ Approve", command=self.approve_booking, bg="#2ecc71", fg="white", width=10, font=("Arial", 9, "bold")).pack(side="left", padx=5)
        
        tk.Button(btn_f, text="🗑️ Delete", command=self.delete, bg=CLR_DANGER, fg="white", width=10).pack(side="left", padx=5)
        tk.Button(btn_f, text="📥 Export CSV", command=self.export_csv, bg="#607d8b", fg="white", width=12).pack(side="left", padx=5)
        
        if model == "Payments":
            tk.Button(btn_f, text="🧾 Receipt", command=lambda: self.preview_receipt(self.tree), bg="#9b59b6", fg="white", width=10).pack(side="left", padx=5)
        self.refresh_table()

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f"{self.current_model}_Export.csv")
        if path:
            with open(path, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(self.get_cols(self.current_model))
                for row_id in self.tree.get_children():
                    writer.writerow(self.tree.item(row_id)['values'])
            messagebox.showinfo("Success", "Data exported successfully!")

    def add(self):
        tbl = self.current_model[:-1].lower() if self.current_model != "Staff" else "staff"
        cols = [i['col'] for i in self.current_input_widgets]
        vals = []
        
        # -- DUPLICATION CHECK LOGIC --
        check_val = None
        if self.current_model == "Clients":
            phone = self.current_input_widgets[1]['w'].get()
            cnic = self.current_input_widgets[3]['w'].get()
            exists = run_query("SELECT Client_ID FROM client WHERE Phone=%s OR CNIC=%s", (phone, cnic))
            if exists: return messagebox.showerror("Duplicate Error", "A client with this Phone or CNIC already exists!")
            
        if self.current_model == "Staff":
            contact = self.current_input_widgets[2]['w'].get()
            exists = run_query("SELECT Staff_ID FROM staff WHERE Contact=%s", (contact,))
            if exists: return messagebox.showerror("Duplicate Error", "A staff member with this Contact number already exists!")

        for i in self.current_input_widgets:
            if isinstance(i['w'], DateEntry): vals.append(i['w'].get_date().strftime('%Y-%m-%d'))
            else:
                val = i['w'].get().split("-")[0]
                if i['col'] in ["Price", "Total_Price", "Paid", "Remaining", "Capacity"]: val = float(val) if val else 0
                vals.append(val)
        try:
            run_query(f"INSERT INTO {tbl} ({','.join(cols)}) VALUES ({','.join(['%s']*len(vals))})", tuple(vals))
            self.refresh_all(); messagebox.showinfo("Success", "Record Added!")
        except Exception as e: messagebox.showerror("Database Error", str(e))

    def refresh_dash_table(self):
        for i in self.dash_tree.get_children(): self.dash_tree.delete(i)
        term = f"%{self.dash_search_var.get()}%"
        query = """SELECT b.Booking_ID, c.Name, v.Venue_Name, pk.Package_Name, (v.Price+pk.Price), b.Booking_Date 
                   FROM booking b JOIN client c ON b.Client_ID=c.Client_ID 
                   JOIN venue v ON b.Venue_ID=v.Venue_ID 
                   JOIN package pk ON b.Package_ID=pk.Package_ID 
                   WHERE c.Name LIKE %s OR v.Venue_Name LIKE %s
                   ORDER BY b.Booking_ID DESC LIMIT 20"""
        data = run_query(query, (term, term))
        for r in data: self.dash_tree.insert("", "end", values=r)

    # ... [Rest of the helper methods (preview_receipt, edit, delete, etc.) remain same as previous version] ...
    def get_cols(self, m):
        d = {
            "Clients": ("Client_ID", "Name", "Phone", "Email", "CNIC"), 
            "Venues": ("Venue_ID", "Venue_Name", "Location", "Capacity", "Price"),
            "Packages": ("Package_ID", "Package_Name", "Description", "Price"),
            "Staff": ("Staff_ID", "Name", "Role", "Contact"),
            "Payments": ("Payment_ID", "Booking_ID", "Total_Price", "Method", "Date", "Paid", "Remaining"), 
            "Bookings": ("Booking_ID", "Client_ID", "Event_Type", "Venue_ID", "Package_ID", "Status", "Booking_Date")
        }
        return d.get(m, ())

    def on_select(self, e):
        if not self.tree.selection(): return
        vals = self.tree.item(self.tree.selection())['values']
        for i, item in enumerate(self.current_input_widgets):
            item['w'].config(state="normal"); item['w'].delete(0, tk.END)
            item['w'].insert(0, str(vals[i+1]))
            if self.current_model == "Payments" and item['col'] in ["Total_Price", "Remaining"]: item['w'].config(state="readonly")

    def edit(self):
        if not self.tree.selection(): return
        pk = self.get_cols(self.current_model)[0]; pk_val = self.tree.item(self.tree.selection())['values'][0]
        tbl = self.current_model[:-1].lower() if self.current_model != "Staff" else "staff"
        cols = [i['col'] for i in self.current_input_widgets]; vals = []
        for i in self.current_input_widgets:
            if isinstance(i['w'], DateEntry): vals.append(i['w'].get_date().strftime('%Y-%m-%d'))
            else: vals.append(i['w'].get().split("-")[0])
        set_q = ",".join([f"{c}=%s" for c in cols])
        run_query(f"UPDATE {tbl} SET {set_q} WHERE {pk}=%s", tuple(vals + [pk_val]))
        self.refresh_all(); messagebox.showinfo("Updated", "Record modified!")

    def delete(self):
        if not self.tree.selection(): return
        if not messagebox.askyesno("Confirm", "Delete this record?"): return
        pk = self.get_cols(self.current_model)[0]; pk_val = self.tree.item(self.tree.selection())['values'][0]
        tbl = self.current_model[:-1].lower() if self.current_model != "Staff" else "staff"
        run_query(f"DELETE FROM {tbl} WHERE {pk}=%s", (pk_val,))
        self.refresh_all()

    def perform_search(self):
        term = f"%{self.search_var.get()}%"
        tbl = self.current_model[:-1].lower() if self.current_model != "Staff" else "staff"
        cols = self.get_cols(self.current_model)
        where = " OR ".join([f"{c} LIKE %s" for c in cols])
        data = run_query(f"SELECT * FROM {tbl} WHERE {where}", tuple([term]*len(cols)))
        for i in self.tree.get_children(): self.tree.delete(i)
        for r in data: self.tree.insert("", "end", values=r)

    def refresh_all(self):
        self.fetch_dropdowns()
        if self.current_model: self.refresh_table()
        else: self.show_dashboard()

    def refresh_table(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        tbl = self.current_model[:-1].lower() if self.current_model != "Staff" else "staff"
        data = run_query(f"SELECT * FROM {tbl}")
        for r in data: self.tree.insert("", "end", values=r)

    def quick_client_add(self):
        win = tk.Toplevel(self.root); win.title("Add New Client"); win.geometry("350x350")
        flds = [("Name", "Entry"), ("Phone", "Entry"), ("Email", "Entry"), ("CNIC", "Entry")]
        ents = {}
        for f, t in flds:
            tk.Label(win, text=f, pady=5).pack()
            e = tk.Entry(win, width=30); e.pack(); ents[f] = e
        def save():
            # Duplicate check for quick add too
            exists = run_query("SELECT Client_ID FROM client WHERE Phone=%s OR CNIC=%s", (ents['Phone'].get(), ents['CNIC'].get()))
            if exists: return messagebox.showerror("Duplicate", "Client already exists!")
            run_query("INSERT INTO client (Name, Phone, Email, CNIC) VALUES (%s,%s,%s,%s)", (ents['Name'].get(), ents['Phone'].get(), ents['Email'].get(), ents['CNIC'].get()))
            self.refresh_all(); win.destroy()
        tk.Button(win, text="Save Client", command=save, bg=CLR_SUCCESS, fg="white", pady=5).pack(pady=20)

    def save_quick_booking(self):
        try:
            cid = self.q_client.get().split("-")[0]
            vid = self.q_venue.get().split("-")[0]
            pid = self.q_pkg.get().split("-")[0]
            dt = self.q_date.get_date().strftime('%Y-%m-%d')
            run_query("INSERT INTO booking (Client_ID, Event_Type, Venue_ID, Package_ID, Status, Booking_Date) VALUES (%s,%s,%s,%s,'Confirmed',%s)", (cid, self.q_etype.get(), vid, pid, dt))
            messagebox.showinfo("Success", "Booking Saved!"); self.show_dashboard()
        except: messagebox.showerror("Error", "Check fields!")

    def pay_auto_fill(self, e):
        bid = self.current_input_widgets[0]['w'].get().split("-")[0]
        res = run_query("SELECT (v.Price+pk.Price) FROM booking b JOIN venue v ON b.Venue_ID=v.Venue_ID JOIN package pk ON b.Package_ID=pk.Package_ID WHERE b.Booking_ID=%s", (bid,))
        if res:
            w = self.current_input_widgets[1]['w']
            w.config(state="normal"); w.delete(0, tk.END); w.insert(0, str(res[0][0])); w.config(state="readonly"); self.pay_math(None)

    def pay_math(self, e):
        try:
            total = float(self.current_input_widgets[1]['w'].get() or 0); paid = float(self.current_input_widgets[4]['w'].get() or 0)
            w = self.current_input_widgets[5]['w']; w.config(state="normal"); w.delete(0, tk.END); w.insert(0, str(total - paid)); w.config(state="readonly")
        except: pass

    def preview_receipt(self, target_tree):
        sel = target_tree.selection()
        if not sel: return messagebox.showwarning("!", "Select a booking first!")
        
        vals = target_tree.item(sel[0])['values']
        bid = vals[0] # The ID from the list

        # 1. SQL JOIN: This ensures Venue A connects to Location A automatically
        query = """
            SELECT 
                b.Booking_ID,      -- [0]
                c.Name,            -- [1]
                b.Event_Type,      -- [2] (e.g. Wedding, Birthday)
                v.Venue_Name,      -- [3] (e.g. Venue A)
                v.Location,        -- [4] (e.g. Karachi)
                pk.Package_Name,   -- [5]
                b.Booking_Date,    -- [6]
                (v.Price + pk.Price) as Total, -- [7]
                COALESCE(p.Paid, 0),           -- [8]
                COALESCE(p.Remaining, (v.Price + pk.Price)) -- [9]
            FROM booking b
            JOIN client c ON b.Client_ID = c.Client_ID
            JOIN venue v ON b.Venue_ID = v.Venue_ID
            JOIN package pk ON b.Package_ID = pk.Package_ID
            LEFT JOIN payment p ON b.Booking_ID = p.Booking_ID
            WHERE b.Booking_ID = %s
        """
        
        data = run_query(query, (bid,))
        if data:
            d = data[0]
            win = tk.Toplevel(self.root)
            win.title(f"Receipt - {d[1]}")
            win.geometry("480x650")
            win.configure(bg="white")

            # --- BRANDING ---
            tk.Label(win, text="NEXUS EVENT MANAGEMENT", font=("Arial", 16, "bold"), bg="white", fg=CLR_SIDEBAR).pack(pady=15)
            tk.Frame(win, height=2, bg=CLR_SIDEBAR).pack(fill="x", padx=40)

            details_f = tk.Frame(win, bg="white", pady=20)
            details_f.pack(fill="x", padx=40)

            # --- THE MISSING FUNCTION (Fixed the error) ---
            def add_info(lbl, val, row_num):
                tk.Label(details_f, text=lbl, font=("Arial", 10, "bold"), bg="white", width=15, anchor="w").grid(row=row_num, column=0, pady=3)
                tk.Label(details_f, text=val, font=("Arial", 10), bg="white").grid(row=row_num, column=1, sticky="w")

            # --- MAPPING DATA TO THE RECEIPT ---
            add_info("BOOKING ID:", f"INV-{d[0]}", 0)
            add_info("CLIENT NAME:", d[1], 1)
            add_info("EVENT TYPE:", d[2], 2)   # Correctly shows Birthday/Wedding
            add_info("VENUE:", d[3], 3)        # Correctly shows Venue A/B
            add_info("LOCATION:", d[4], 4)     # Correctly shows Location for A or B
            add_info("EVENT DATE:", d[6], 5)

            # --- FINANCIALS (Already in your code) ---
            pay_f = tk.Frame(win, bg="#f8f9fa", pady=15, padx=20, bd=1, relief="groove")
            pay_f.pack(fill="x", padx=40, pady=20)

            tk.Label(pay_f, text=f"Total Amount: ${d[7]:,.2f}", font=("Arial", 11, "bold"), bg="#f8f9fa").pack(anchor="e")
            tk.Label(pay_f, text=f"Paid: ${d[8]:,.2f}", fg=CLR_SUCCESS, bg="#f8f9fa").pack(anchor="e")
            tk.Frame(pay_f, height=1, bg="gray").pack(fill="x", pady=5)
            tk.Label(pay_f, text=f"BALANCE DUE: ${d[9]:,.2f}", font=("Arial", 12, "bold"), fg=CLR_DANGER, bg="#f8f9fa").pack(anchor="e")

            # --- THE MISSING BUTTONS ---
            btn_f = tk.Frame(win, bg="white")
            btn_f.pack(pady=20)

            # SAVE BUTTON
            tk.Button(btn_f, text="💾 SAVE RECEIPT", command=lambda: self.save_pdf(d, win), 
                      bg=CLR_ACCENT, fg="white", font=("Arial", 10, "bold"), padx=20, pady=5).pack(side="left", padx=10)
            
            # CLOSE BUTTON
            tk.Button(btn_f, text="CLOSE", command=win.destroy, 
                      bg="#95a5a6", fg="white", font=("Arial", 10), padx=15).pack(side="left", padx=10)

    def save_pdf(self, data, window):
        from tkinter import filedialog
        
        # Data mapping from our query
        file_content = f"""
        ================================================
                    NEXUS EVENT SOLUTIONS
                   OFFICIAL PAYMENT RECEIPT
        ================================================
        Invoice No:    INV-2026-{data[0]}
        Date:          {date.today()}
        
        CLIENT DETAILS
        ------------------------------------------------
        Client Name:   {data[1]}
        Contact:       {data[2]}
        
        EVENT DETAILS
        ------------------------------------------------
        Event Type:    {data[2]}
        Venue Name:    {data[3]}
        Location:      {data[4]}
        Event Date:    {data[6]}
        
        BILLING SUMMARY
        ------------------------------------------------
        Total Amount:  ${data[7]:,.2f}
        Amount Paid:   ${data[8]:,.2f}
        Balance Due:   ${data[9]:,.2f}
        
        Status:        {"FULLY PAID" if data[9] <= 0 else "BALANCE PENDING"}
        ------------------------------------------------
        Thank you for choosing Nexus Events!
        ================================================
        """
        
        path = filedialog.asksaveasfilename(defaultextension=".txt", 
                                             filetypes=[("Text files", "*.txt"), ("PDF files", "*.pdf")],
                                             initialfile=f"Receipt_INV_{data[0]}")
        if path:
            with open(path, "w") as f:
                f.write(file_content)
            messagebox.showinfo("Success", f"Receipt saved to {path}")
            window.destroy()
if __name__ == "__main__":
    root = tk.Tk(); app = EventApp(root); root.mainloop()