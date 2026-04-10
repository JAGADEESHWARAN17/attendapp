import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import time
from fpdf import FPDF # pip install fpdf2

# --- DATABASE UTILITY FUNCTIONS ---
def get_db_connection():
    conn = sqlite3.connect('attendance_pro.db', check_same_thread=False, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS classes (id INTEGER PRIMARY KEY, branch TEXT, section TEXT)')
    
    # "name" column removed to identify students strictly by reg_no
    c.execute('''CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY, 
                    class_id INTEGER, 
                    reg_no TEXT, 
                    UNIQUE(class_id, reg_no)
                 )''')
                 
    c.execute('CREATE TABLE IF NOT EXISTS attendance (id INTEGER PRIMARY KEY, student_id INTEGER, status TEXT, date TEXT)')
    conn.commit()
    conn.close()

init_db()

# --- ENHANCED PDF GENERATION FUNCTION ---
def create_pdf(df, class_name, report_date, filter_status, is_all_time=False):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"{class_name} Attendance List", ln=True, align='C')
    pdf.ln(5)
    
    # Adjusted widths to fill space without the Name column
    w_reg = 95
    w_status = 95

    def draw_header():
        pdf.set_font("Arial", 'B', 10)
        pdf.set_fill_color(0, 31, 63)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(w_reg, 10, "Reg No", border=1, fill=True, align='C')
        pdf.cell(w_status, 10, "Status", border=1, fill=True, align='C')
        pdf.ln()
        pdf.set_text_color(0, 0, 0)

    if not is_all_time:
        pdf.set_font("Arial", 'I', 11)
        pdf.cell(0, 10, f"Date: {report_date}  |  Filter: {filter_status}", ln=True, align='C')
        pdf.ln(2)
        draw_header()
        pdf.set_font("Arial", size=10)
        for _, row in df.iterrows():
            pdf.cell(w_reg, 9, str(row['Reg No']), border=1, align='C')
            pdf.cell(w_status, 9, str(row['Status']), border=1, align='C')
            pdf.ln()
    else:
        dates = df['Date'].unique()
        for d in dates:
            pdf.set_font("Arial", 'B', 12)
            pdf.set_fill_color(230, 230, 230)
            pdf.cell(0, 10, f"Date: {d}", border=0, ln=True, align='L', fill=True)
            draw_header()
            pdf.set_font("Arial", size=10)
            date_df = df[df['Date'] == d]
            for _, row in date_df.iterrows():
                pdf.cell(w_reg, 9, str(row['Reg No']), border=1, align='C')
                pdf.cell(w_status, 9, str(row['Status']), border=1, align='C')
                pdf.ln()
            pdf.ln(5)

    return bytes(pdf.output())

# --- CUSTOM STYLING ---
# initial_sidebar_state set to "collapsed" to hide it automatically on load
st.set_page_config(page_title="Attendify",page_icon="Aicon.png", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    /* Global Background and Text */
    .stApp { background-color: #FFFFFF !important; color: #31333F !important; }
    .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp label { color: #31333F !important; }

    .greeting-box {
        background-image: linear-gradient(to right, #001f3f, #003366);
        padding: 30px; border-radius: 15px; color: white !important; margin-bottom: 25px;
    }
    .greeting-box h1, .greeting-box p, .greeting-box h3 { color: white !important; }
    
    /* --- BULLETPROOF STUDENT CARD TEXT COLOR --- */
    .student-card, 
    .student-card p, 
    .student-card h1, 
    .student-card div, 
    .student-card span {
        color: #FFFFFF !important;
    }

    /* Sidebar Layout */
    section[data-testid="stSidebar"] { background-color: #001f3f !important; }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p { color: white !important; }

    /* ALL BUTTONS */
    div.stButton > button,
    div.stDownloadButton > button,
    div.stFormSubmitButton > button {
        background-image: linear-gradient(to right, #001f3f, #003366) !important;
        background-color: transparent !important;
        color: white !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        border-radius: 12px !important;
        padding: 10px 20px !important;
        font-weight: bold !important;
        transition: all 0.2s ease-in-out !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2) !important;
        width: 100%;
    }

    div.stButton > button p,
    div.stDownloadButton > button p,
    div.stFormSubmitButton > button p {
        color: white !important;
    }

    div.stButton > button:hover,
    div.stDownloadButton > button:hover,
    div.stFormSubmitButton > button:hover {
        border-color: white !important;
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.4) !important;
    }

    div.stButton > button:active,
    div.stDownloadButton > button:active,
    div.stFormSubmitButton > button:active {
        transform: scale(0.96) !important;
        box-shadow: 0 0 25px 8px rgba(0, 51, 102, 0.8) !important;
        backdrop-filter: blur(8px) !important;
        background-image: linear-gradient(to right, #003366, #001f3f) !important;
    }
    
    /* SIDEBAR COLLAPSE BUTTON */
    button[data-testid="stSidebarCollapseButton"] {
        background-image: linear-gradient(to right, #001f3f, #003366) !important;
        background-color: transparent !important;
        border: 1px solid rgba(255,255,255,0.3) !important;
        border-radius: 8px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3) !important;
        transition: all 0.2s ease-in-out !important;
        opacity: 1 !important;
        visibility: visible !important;
    }

    button[data-testid="stSidebarCollapseButton"]:hover {
        box-shadow: 0 4px 10px rgba(0,0,0,0.5) !important;
        border-color: white !important;
    }

    button[data-testid="stSidebarCollapseButton"]:active {
        transform: scale(0.96) !important;
        backdrop-filter: blur(8px) !important;
        box-shadow: 0 0 12px 4px rgba(0, 51, 102, 0.7) !important;
    }

    button[data-testid="stSidebarCollapseButton"] svg,
    button[data-testid="stSidebarCollapseButton"] svg path {
        fill: white !important;
        stroke: white !important;
    }

    /* Force collapse button container to always show */
    [data-testid="collapsedControl"],
    div[class*="collapsedControl"] {
        opacity: 1 !important;
        visibility: visible !important;
    }

    /* Form Fields */
    div[data-baseweb="select"] > div,
    div[data-testid="stTextInput"] input {
        background-color: #F0F2F5 !important;
        color: #31333F !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR NAVIGATION ---
with st.sidebar:
    st.markdown("<h1 style='text-align: center; color: white;'>Menu</h1>", unsafe_allow_html=True)
    if 'menu_choice' not in st.session_state: st.session_state.menu_choice = "Home"
    if st.button("🛖 Home"): st.session_state.menu_choice = "Home"
    if st.button("➕ Add New Class"): st.session_state.menu_choice = "Add New Class"
    if st.button("👤 Add Student"): st.session_state.menu_choice = "Add Student"
    if st.button("📑 Take Attendance"): st.session_state.menu_choice = "Take Attendance"
    if st.button("📔 View Attendance"): st.session_state.menu_choice = "View Attendance"
    if st.button("🗑️ Remove Class"): st.session_state.menu_choice = "Remove Class"

choice = st.session_state.menu_choice
now = datetime.now()
today_str = now.strftime("%Y-%m-%d")

# --- 1. HOME ---
if choice == "Home":
    conn = get_db_connection()
    st.markdown(f"""<div class="greeting-box"><h1>Good Morning!</h1><p>Today is {now.strftime('%A, %d %B')}</p><h3>Have a Great Day :)</h3></div>""", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    classes_taken_today = pd.read_sql(f"SELECT COUNT(DISTINCT s.class_id) as count FROM attendance a JOIN students s ON a.student_id = s.id WHERE a.date = '{today_str}'", conn).iloc[0]['count']
    with col1: st.metric("Total Classes", len(pd.read_sql("SELECT id FROM classes", conn)))
    with col2: st.metric("Total Students", len(pd.read_sql("SELECT id FROM students", conn)))
    with col3: st.metric("Attendance Marked (Classes)", int(classes_taken_today))
    conn.close()

# --- 2. ADD NEW CLASS ---
elif choice == "Add New Class":
    st.header("Class Manager")
    with st.form("main_class_form", clear_on_submit=True):
        dept = st.text_input("Department").upper()
        branch = st.text_input("Branch").upper()
        section = st.text_input("Section").upper()
        if st.form_submit_button("Create Class"):
            # Strict validation for single caps alphabet
            if not (len(section) == 1 and section.isalpha() and section.isupper()):
                st.error("Section must be a single capital letter (e.g., A, B, C).")
            elif dept and branch and section:
                fb, fs = f"{dept} {branch}", section
                conn = get_db_connection()
                if conn.execute("SELECT id FROM classes WHERE branch=? AND section=?", (fb, fs)).fetchone():
                    st.error("Class exists!")
                else:
                    conn.execute("INSERT INTO classes (branch, section) VALUES (?, ?)", (fb, fs))
                    conn.commit()
                    st.success(f"{fb} {fs} -- Has Created!"); time.sleep(1); st.rerun()
                conn.close()

# --- 3. ADD STUDENT ---
elif choice == "Add Student":
    st.header("👤 Add New Student")
    conn = get_db_connection()
    classes = conn.execute("SELECT id, branch, section FROM classes").fetchall()
    class_map = {f"{b} {s}": i for i, b, s in classes}
    if class_map:
        opts = list(class_map.keys())
        if 'last_selected_class' not in st.session_state or st.session_state.last_selected_class not in opts:
            st.session_state.last_selected_class = opts[0]
        sel_class = st.selectbox("Assign to Class", opts, index=opts.index(st.session_state.last_selected_class))
        st.session_state.last_selected_class = sel_class
        with st.form("add_student_form", clear_on_submit=True):
            rn = st.text_input("Registration Number")
            if st.form_submit_button("Save Student"):
                if rn.strip():
                    current_class_id = class_map[sel_class]
                    if conn.execute("SELECT id FROM students WHERE reg_no=? AND class_id=?", (rn, current_class_id)).fetchone():
                        st.error(f"Reg No {rn} already exists in {sel_class}!")
                    else:
                        conn.execute("INSERT INTO students (class_id, reg_no) VALUES (?,?)", (current_class_id, rn))
                        conn.commit(); st.success(f"Reg No {rn} Added!"); time.sleep(1); st.rerun()
    st.divider(); st.subheader("Student Directory")
    for cid, b, s in classes:
        count = conn.execute("SELECT COUNT(*) FROM students WHERE class_id=?", (cid,)).fetchone()[0]
        with st.expander(f"{b} {s} ({count} students)"):
            students = conn.execute("SELECT id, reg_no FROM students WHERE class_id=? ORDER BY CAST(reg_no AS INTEGER) ASC", (cid,)).fetchall()
            for sid, sr in students:
                c1, c2 = st.columns([7, 1])
                c1.write(f"**Roll No: {sr}**")
                if c2.button("❌", key=f"del_{sid}"): conn.execute("DELETE FROM students WHERE id=?", (sid,)); conn.commit(); st.rerun()
    conn.close()

# --- 4. TAKE ATTENDANCE ---
elif choice == "Take Attendance":
    st.header("Take Attendance")
    conn = get_db_connection()
    classes = conn.execute("SELECT id, branch, section FROM classes").fetchall()
    class_options = {f"{b} {s}": i for i, b, s in classes}
    if class_options:
        target = st.selectbox("Select Class", list(class_options.keys()))
        if 'current_attendance_class' not in st.session_state: st.session_state.current_attendance_class = target
        if target != st.session_state.current_attendance_class:
            st.session_state.current_attendance_class = target; st.session_state.pop('replace_confirmed', None); st.session_state.idx = 0; st.session_state.log = []
        t_id = class_options[target]
        if conn.execute("SELECT COUNT(*) FROM attendance WHERE student_id IN (SELECT id FROM students WHERE class_id=?) AND date=?", (t_id, today_str)).fetchone()[0] > 0 and 'replace_confirmed' not in st.session_state:
            st.warning("Attendance has already been taken!"); c1, c2 = st.columns(2)
            if c1.button("Re-Take Attendance"): st.session_state.replace_confirmed = True; st.rerun()
            if c2.button("Go Back"): st.session_state.menu_choice = "Home"; st.rerun()
        else:
            students = conn.execute("SELECT id, reg_no FROM students WHERE class_id=? ORDER BY CAST(reg_no AS INTEGER) ASC", (t_id,)).fetchall()
            if students:
                if 'idx' not in st.session_state: st.session_state.idx = 0
                if 'log' not in st.session_state: st.session_state.log = []
                if st.session_state.idx < len(students):
                    curr = students[st.session_state.idx]
                    
                    # ---> UPDATED PREMIUM STUDENT CARD <---
                    st.markdown(f"""
                        <div class="student-card" style="
                            background-image: linear-gradient(to right, #001f3f, #003366);
                            padding: 35px 20px; 
                            border-radius: 20px; 
                            text-align: center; 
                            border: 1px solid rgba(255,255,255,0.2); 
                            box-shadow: 0 8px 20px rgba(0,0,0,0.3); 
                            margin-bottom: 20px;
                        ">
                            <h1 style="font-size: 3rem !important; margin-bottom: 20px !important; font-weight: 800; letter-spacing: 1px; text-shadow: 1px 1px 4px rgba(0,0,0,0.4);">
                                Roll No: {curr[1]}
                            </h1>
                            <div style="display: inline-block; background-color: rgba(255,255,255,0.1); padding: 8px 20px; border-radius: 50px; border: 1px solid rgba(255,255,255,0.2);">
                                <span style="font-size: 1rem !important; font-weight: bold; letter-spacing: 1.5px;">
                                    STUDENT {st.session_state.idx + 1} OF {len(students)}
                                </span>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    # ----------------------------------------
                    
                    _, c1, c2, c3, _ = st.columns([2, 2, 2, 2, 0.5])
                    if c1.button("✅ PRESENT"): st.session_state.log.append((curr[0], "Present")); st.session_state.idx += 1; st.rerun()
                    if c2.button("❌ ABSENT"): st.session_state.log.append((curr[0], "Absent")); st.session_state.idx += 1; st.rerun()
                    if c3.button("🔷 OD"): st.session_state.log.append((curr[0], "OD")); st.session_state.idx += 1; st.rerun()
                    _, bc, _ = st.columns([4.34, 1, 4])
                    if st.session_state.idx > 0 and bc.button("BACK"): st.session_state.idx -= 1; st.session_state.log.pop(); st.rerun()
                else:
                    st.balloons()
                    if st.button("Finalize and Save"):
                        if st.session_state.get('replace_confirmed'): conn.execute("DELETE FROM attendance WHERE date=? AND student_id IN (SELECT id FROM students WHERE class_id=?)", (today_str, t_id))
                        for sid, stat in st.session_state.log: conn.execute("INSERT INTO attendance (student_id, status, date) VALUES (?,?,?)", (sid, stat, today_str))
                        conn.commit(); st.session_state.idx = 0; st.session_state.log = []; st.session_state.pop('replace_confirmed', None); st.success("Saved!"); time.sleep(1); st.rerun()
    conn.close()

# --- 5. VIEW ATTENDANCE ---
elif choice == "View Attendance":
    # Inject scoped CSS specifically for this page to reduce layout font sizes
    st.markdown("""
        <style>
        /* Zoom out the canvas table wrapper to scale down its contents */
        [data-testid="stDataEditor"] > div { zoom: 0.85; }
        /* Reduce font sizes on general page elements in this block */
        .stSelectbox label, .stDateInput label { font-size: 0.85rem !important; }
        </style>
    """, unsafe_allow_html=True)

    st.header("History")
    col1, col2, col3 = st.columns([2, 2, 2])
    v_date = col1.date_input("Select Date", now)
    conn = get_db_connection()
    classes = conn.execute("SELECT id, branch, section FROM classes").fetchall()
    class_map = {f"{b} {s}": i for i, b, s in classes}
    
    if class_map:
        target = col2.selectbox("Select Class", list(class_map.keys()))
        status_filter = col3.selectbox("Filter Status", ["All", "Present", "Absent", "OD"])
        
        query = "SELECT a.id as 'ID', s.reg_no as 'Reg No', a.status as 'Status' FROM attendance a JOIN students s ON a.student_id = s.id WHERE s.class_id = ? AND a.date = ?"
        params = [class_map[target], v_date.strftime("%Y-%m-%d")]
        
        if status_filter != "All": 
            query += " AND a.status = ?"
            params.append(status_filter)
            
        query += " ORDER BY CAST(s.reg_no AS INTEGER) ASC"
        df = pd.read_sql_query(query, conn, params=params)
        
        if not df.empty:
            edited_df = st.data_editor(
                df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "ID": None, 
                    "Reg No": st.column_config.TextColumn("Reg No", disabled=True),
                    "Status": st.column_config.SelectboxColumn(
                        "Status",
                        help="Click the pencil icon to edit",
                        options=["Present", "Absent", "OD"],
                        required=True
                    )
                }
            )
            
            if not df.equals(edited_df):
                if st.button("Save Changes"):
                    diff = edited_df
