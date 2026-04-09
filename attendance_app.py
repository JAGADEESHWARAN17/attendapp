import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import time

# --- DATABASE UTILITY FUNCTIONS ---
def get_db_connection():
    """Helper to get a fresh database connection and prevent locking."""
    conn = sqlite3.connect('attendance_pro.db', check_same_thread=False, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

def init_db():
    """Initializes the database tables."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS classes (id INTEGER PRIMARY KEY, branch TEXT, section TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY, class_id INTEGER, name TEXT, reg_no TEXT, UNIQUE(reg_no))')
    c.execute('CREATE TABLE IF NOT EXISTS attendance (id INTEGER PRIMARY KEY, student_id INTEGER, status TEXT, date TEXT)')
    conn.commit()
    conn.close()

# Initialize DB on startup
init_db()

# --- CUSTOM STYLING (UI UNTOUCHED) ---
st.set_page_config(page_title="Attendance X", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF !important; color: #31333F !important; }
    .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp label { color: #31333F !important; }
    .greeting-box {
        background-image: linear-gradient(to right, #001f3f, #003366);
        padding: 30px; border-radius: 15px; color: white !important; margin-bottom: 25px;
    }
    .greeting-box h1, .greeting-box p, .greeting-box h3 { color: white !important; }
    section[data-testid="stSidebar"] { background-color: #001f3f !important; }
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] p { color: white !important; }
    .stButton > button, .stButton > button p, div[data-testid="stForm"] button { color: white !important; }
    button[kind="secondary"] { color: white !important; }
    section[data-testid="stSidebar"] .stButton > button {
        background-color: transparent !important; border: 1px solid rgba(255,255,255,0.2) !important;
        width: 100%; text-align: left; padding: 10px 15px; border-radius: 8px; margin-bottom: 5px;
    }
    div[data-testid="column"] button { width: 100% !important; margin: 0 auto; }
    .stButton>button { background-image: linear-gradient(to right, #001f3f, #003366); border-radius: 12px; border: none; padding: 10px 20px; }
    div[data-baseweb="select"] > div, div[data-testid="stTextInput"] input { background-color: #F0F2F5 !important; color: #31333F !important; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR NAVIGATION ---
with st.sidebar:
    st.markdown("<h1 style='text-align: center; color: white;'>Menu</h1>", unsafe_allow_html=True)
    if 'menu_choice' not in st.session_state: st.session_state.menu_choice = "Home"
    if st.button("🏠 Home"): st.session_state.menu_choice = "Home"
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
    st.markdown(f"""<div class="greeting-box"><h1>Good Morning! </h1><p>Today is {now.strftime('%A, %d %B')}</p><h3>Have a Great Day :)</h3></div>""", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    
    # Logic Update: Count distinct classes that have entries in the attendance table for today
    classes_taken_today = pd.read_sql(f"""
        SELECT COUNT(DISTINCT s.class_id) as count 
        FROM attendance a 
        JOIN students s ON a.student_id = s.id 
        WHERE a.date = '{today_str}'
    """, conn).iloc[0]['count']

    with col1: st.metric("Total Classes", len(pd.read_sql("SELECT id FROM classes", conn)))
    with col2: st.metric("Total Students", len(pd.read_sql("SELECT id FROM students", conn)))
    with col3: st.metric("Attendance Marked (Classes)", int(classes_taken_today))
    conn.close()

# --- 2. ADD NEW CLASS ---
elif choice == "Add New Class":
    st.header("Class Manager")
    with st.form("main_class_form", clear_on_submit=True):
        dept = st.text_input("Department").upper(); branch = st.text_input("Branch").upper(); section = st.text_input("Section").upper()
        if st.form_submit_button("Create Class"):
            if dept and branch and section:
                fb, fs = f"{dept} {branch}", section
                conn = get_db_connection()
                c = conn.cursor()
                if c.execute("SELECT id FROM classes WHERE branch=? AND section=?", (fb, fs)).fetchone():
                    st.error(f"Class '{fb} {fs}' already exists!")
                else:
                    c.execute("INSERT INTO classes (branch, section) VALUES (?, ?)", (fb, fs))
                    conn.commit()
                    st.success(f"✅ Class '{fb} {fs}' Created Successfully!"); time.sleep(1); st.rerun()
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
            sn = st.text_input("Full Name"); rn = st.text_input("Registration Number")
            if st.form_submit_button("Save Student"):
                if sn.strip() != "" and rn.strip() != "":
                    check_exists = conn.execute("SELECT name FROM students WHERE reg_no=?", (rn,)).fetchone()
                    if check_exists:
                        st.error(f"Student '{check_exists[0]}' already exists with Registration No '{rn}'!")
                    else:
                        try:
                            conn.execute("INSERT INTO students (class_id, name, reg_no) VALUES (?,?,?)", (class_map[sel_class], sn, rn))
                            conn.commit()
                            st.success(f"✅ Student '{sn}' added to {sel_class}!")
                            time.sleep(1); st.rerun()
                        except Exception as e:
                            st.error(f"Error saving to database. Please try again.")
                else: st.error("Please fill all fields.")
    else: st.warning("Create a class first!")

    st.divider(); st.subheader("Student Directory")
    for cid, b, s in classes:
        with st.expander(f"{b} {s}"):
            students = conn.execute("SELECT id, name, reg_no FROM students WHERE class_id=? ORDER BY reg_no ASC", (cid,)).fetchall()
            for sid, sn, sr in students:
                col = st.columns([7,1])
                col[0].write(f"**{sr}** - {sn}")
                if col[1].button("❌", key=f"del_{sid}"): 
                    conn.execute("DELETE FROM students WHERE id=?", (sid,))
                    conn.commit(); st.rerun()
    conn.close()

# --- 4. TAKE ATTENDANCE ---
elif choice == "Take Attendance":
    st.header("📑 Take Attendance")
    conn = get_db_connection()
    classes = conn.execute("SELECT id, branch, section FROM classes").fetchall()
    class_options = {f"{b} {s}": i for i, b, s in classes}
    
    if class_options:
        if 'current_attendance_class' not in st.session_state:
            st.session_state.current_attendance_class = list(class_options.keys())[0]

        target = st.selectbox("Select Class", list(class_options.keys()))
        
        # Reset state if class selection changes
        if target != st.session_state.current_attendance_class:
            st.session_state.current_attendance_class = target
            st.session_state.pop('replace_confirmed', None)
            st.session_state.idx = 0
            st.session_state.log = []

        t_id = class_options[target]
        existing = conn.execute("SELECT COUNT(*) FROM attendance WHERE student_id IN (SELECT id FROM students WHERE class_id=?) AND date=?", (t_id, today_str)).fetchone()[0]
        
        if existing > 0 and 'replace_confirmed' not in st.session_state:
            st.warning(f"⚠️ Attendance for {target} already exists today.")
            col_a, col_b = st.columns(2)
            if col_a.button("🔄 REPLACE EXISTING"): 
                st.session_state.replace_confirmed = True
                st.rerun()
            if col_b.button("🔙 BACK"): 
                st.session_state.menu_choice = "Home"
                st.rerun()
        else:
            students = conn.execute("SELECT id, name, reg_no FROM students WHERE class_id=? ORDER BY reg_no ASC", (t_id,)).fetchall()
            if students:
                if 'idx' not in st.session_state: st.session_state.idx = 0
                if 'log' not in st.session_state: st.session_state.log = []

                if st.session_state.idx < len(students):
                    curr = students[st.session_state.idx]
                    st.markdown(f"""<div style="background-color: white; padding: 40px; border-radius: 20px; text-align: center; border: 2px solid #001f3f; margin-bottom: 20px;">
                        <h1 style="color: #001f3f;">{curr[1]}</h1><p>Roll: {curr[2]}</p>
                        <p><b>Student {st.session_state.idx + 1} of {len(students)}</b></p></div>""", unsafe_allow_html=True)
                    _, c1, c2, c3, _ = st.columns([2, 2, 2, 2, 0.5])
                    if c1.button("✅ PRESENT"): st.session_state.log.append((curr[0], "Present")); st.session_state.idx += 1; st.rerun()
                    if c2.button("❌ ABSENT"): st.session_state.log.append((curr[0], "Absent")); st.session_state.idx += 1; st.rerun()
                    if c3.button("🔷 OD"): st.session_state.log.append((curr[0], "OD")); st.session_state.idx += 1; st.rerun()
                    _, bc, _ = st.columns([4.34, 1, 4])
                    if st.session_state.idx > 0 and bc.button("BACK"): st.session_state.idx -= 1; st.session_state.log.pop(); st.rerun()
                else:
                    st.balloons()
                    if st.button("Finalize and Save Attendance"):
                        if st.session_state.get('replace_confirmed'):
                            conn.execute("DELETE FROM attendance WHERE date=? AND student_id IN (SELECT id FROM students WHERE class_id=?)", (today_str, t_id))
                        for sid, stat in st.session_state.log:
                            conn.execute("INSERT INTO attendance (student_id, status, date) VALUES (?,?,?)", (sid, stat, today_str))
                        conn.commit()
                        st.session_state.idx = 0; st.session_state.log = []; st.session_state.pop('replace_confirmed', None)
                        st.success("Attendance Saved!"); time.sleep(1); st.rerun()
            else: st.info("No students found.")
    conn.close()

# --- 5. VIEW ATTENDANCE ---
elif choice == "View Attendance":
    st.header("📔 History")
    col1, col2 = st.columns(2)
    v_date = col1.date_input("Date", now)
    conn = get_db_connection()
    classes = conn.execute("SELECT id, branch, section FROM classes").fetchall()
    class_map = {f"{b} {s}": i for i, b, s in classes}
    if class_map:
        target = col2.selectbox("Class", list(class_map.keys()))
        df = pd.read_sql_query("SELECT s.reg_no as 'Reg No', s.name as 'Name', a.status as 'Status' FROM attendance a JOIN students s ON a.student_id = s.id WHERE s.class_id = ? AND a.date = ?", conn, params=(class_map[target], v_date.strftime("%Y-%m-%d")))
        st.table(df)
    conn.close()

# --- 6. REMOVE CLASS ---
elif choice == "Remove Class":
    st.header("🗑️ Remove Class")
    conn = get_db_connection()
    classes = conn.execute("SELECT id, branch, section FROM classes").fetchall()
    for cid, b, s in classes:
        if st.button(f"Delete {b} {s}", key=f"rm_{cid}"):
            conn.execute("DELETE FROM classes WHERE id=?", (cid,))
            conn.execute("DELETE FROM students WHERE class_id=?", (cid,))
            conn.commit(); st.success(f"Deleted '{b} {s}' Successfully!"); time.sleep(1); st.rerun()
    conn.close()
