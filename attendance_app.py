import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import time
import hashlib
import os
from fpdf import FPDF

# ─────────────────────────────────────────────
#  AUTH DATABASE  (shared, stores only users)
# ─────────────────────────────────────────────
AUTH_DB = "auth.db"

def get_auth_conn():
    conn = sqlite3.connect(AUTH_DB, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_auth_db():
    conn = get_auth_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY,
            username TEXT    UNIQUE NOT NULL,
            password TEXT    NOT NULL,
            name     TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username: str, password: str, name: str) -> tuple[bool, str]:
    conn = get_auth_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, password, name) VALUES (?, ?, ?)",
            (username.strip().lower(), hash_pw(password), name.strip())
        )
        conn.commit()
        return True, "Account created!"
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    finally:
        conn.close()

def login_user(username: str, password: str):
    conn = get_auth_conn()
    row = conn.execute(
        "SELECT id, name FROM users WHERE username=? AND password=?",
        (username.strip().lower(), hash_pw(password))
    ).fetchone()
    conn.close()
    return row  # (id, name) or None

init_auth_db()


# ─────────────────────────────────────────────
#  PER-USER ATTENDANCE DATABASE
# ─────────────────────────────────────────────
DB_FOLDER = "user_dbs"
os.makedirs(DB_FOLDER, exist_ok=True)

def get_db_path(username: str) -> str:
    safe = "".join(c for c in username if c.isalnum() or c in "_-")
    return os.path.join(DB_FOLDER, f"{safe}.db")

def get_db_conn(username: str):
    conn = sqlite3.connect(get_db_path(username), check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_user_db(username: str):
    conn = get_db_conn(username)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS classes (id INTEGER PRIMARY KEY, branch TEXT, section TEXT)")
    c.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id       INTEGER PRIMARY KEY,
            class_id INTEGER,
            name     TEXT,
            reg_no   TEXT,
            UNIQUE(class_id, reg_no)
        )
    """)
    c.execute("CREATE TABLE IF NOT EXISTS attendance (id INTEGER PRIMARY KEY, student_id INTEGER, status TEXT, date TEXT)")
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
#  PDF GENERATOR
# ─────────────────────────────────────────────
def create_pdf(df, class_name, report_date, filter_status, is_all_time=False):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"{class_name} Attendance List", ln=True, align='C')
    pdf.ln(5)
    w_reg, w_name, w_status = 40, 110, 40

    def draw_header():
        pdf.set_font("Arial", 'B', 10)
        pdf.set_fill_color(0, 31, 63)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(w_reg,    10, "Reg No",       border=1, fill=True, align='C')
        pdf.cell(w_name,   10, "Student Name", border=1, fill=True, align='C')
        pdf.cell(w_status, 10, "Status",       border=1, fill=True, align='C')
        pdf.ln()
        pdf.set_text_color(0, 0, 0)

    if not is_all_time:
        pdf.set_font("Arial", 'I', 11)
        pdf.cell(0, 10, f"Date: {report_date}  |  Filter: {filter_status}", ln=True, align='C')
        pdf.ln(2)
        draw_header()
        pdf.set_font("Arial", size=10)
        for _, row in df.iterrows():
            pdf.cell(w_reg,    9, str(row['Reg No']), border=1, align='C')
            pdf.cell(w_name,   9, f" {str(row['Name'])}", border=1, align='L')
            pdf.cell(w_status, 9, str(row['Status']), border=1, align='C')
            pdf.ln()
    else:
        for d in df['Date'].unique():
            pdf.set_font("Arial", 'B', 12)
            pdf.set_fill_color(230, 230, 230)
            pdf.cell(0, 10, f"Date: {d}", border=0, ln=True, align='L', fill=True)
            draw_header()
            pdf.set_font("Arial", size=10)
            for _, row in df[df['Date'] == d].iterrows():
                pdf.cell(w_reg,    9, str(row['Reg No']), border=1, align='C')
                pdf.cell(w_name,   9, f" {str(row['Name'])}", border=1, align='L')
                pdf.cell(w_status, 9, str(row['Status']), border=1, align='C')
                pdf.ln()
            pdf.ln(5)
    return bytes(pdf.output())


# ─────────────────────────────────────────────
#  PAGE CONFIG & GLOBAL STYLES
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Attendify",
    page_icon="Aicon.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.stApp { background-color: #FFFFFF !important; color: #31333F !important; }
.stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp label { color: #31333F !important; }

.greeting-box {
    background-image: linear-gradient(to right, #001f3f, #003366);
    padding: 30px; border-radius: 15px; color: white !important; margin-bottom: 25px;
}
.greeting-box h1, .greeting-box p, .greeting-box h3 { color: white !important; }

.student-card, .student-card p, .student-card h1,
.student-card div, .student-card span { color: #FFFFFF !important; }

/* Auth card */
.auth-card {
    background: linear-gradient(135deg, #001f3f 0%, #003366 100%);
    padding: 40px; border-radius: 20px; max-width: 440px;
    margin: 60px auto 0; box-shadow: 0 20px 60px rgba(0,31,63,0.35);
}
.auth-card h2 { color: white !important; text-align: center; margin-bottom: 6px; }
.auth-card p  { color: rgba(255,255,255,0.7) !important; text-align: center; margin-bottom: 24px; }

/* Sidebar */
section[data-testid="stSidebar"] { background-color: #001f3f !important; }
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p { color: white !important; }

/* Buttons */
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
    box-shadow: 0 4px 6px rgba(0,0,0,0.2) !important;
    width: 100%;
}
div.stButton > button p,
div.stDownloadButton > button p,
div.stFormSubmitButton > button p { color: white !important; }
div.stButton > button:hover,
div.stDownloadButton > button:hover,
div.stFormSubmitButton > button:hover {
    border-color: white !important;
    box-shadow: 0 6px 12px rgba(0,0,0,0.4) !important;
}
div.stButton > button:active,
div.stDownloadButton > button:active,
div.stFormSubmitButton > button:active {
    transform: scale(0.96) !important;
    box-shadow: 0 0 25px 8px rgba(0,51,102,0.8) !important;
}

/* Sidebar collapse button */
button[data-testid="stSidebarCollapseButton"] {
    background-image: linear-gradient(to right, #001f3f, #003366) !important;
    border: 1px solid rgba(255,255,255,0.3) !important;
    border-radius: 8px !important;
}
button[data-testid="stSidebarCollapseButton"] svg,
button[data-testid="stSidebarCollapseButton"] svg path {
    fill: white !important; stroke: white !important;
}

/* Form fields */
div[data-baseweb="select"] > div,
div[data-testid="stTextInput"] input {
    background-color: #F0F2F5 !important;
    color: #31333F !important;
}

/* ── Attendance list rows ── */
.att-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
    border-radius: 12px;
    margin-bottom: 8px;
    background: #f7f9fc;
    border: 1px solid #e0e4ea;
    gap: 8px;
}
.att-row:nth-child(even) { background: #eef1f7; }
.att-name  { font-weight: 600; font-size: 1rem; flex: 1; color: #1a1a2e !important; }
.att-reg   { font-size: 0.85rem; color: #555 !important; margin-right: 12px; min-width: 60px; }
.badge-P   { background:#00875a; color:white; border-radius:8px; padding:4px 14px; font-weight:700; font-size:0.85rem; }
.badge-A   { background:#c0392b; color:white; border-radius:8px; padding:4px 14px; font-weight:700; font-size:0.85rem; }
.badge-O   { background:#2471a3; color:white; border-radius:8px; padding:4px 14px; font-weight:700; font-size:0.85rem; }
.badge-N   { background:#aaa;    color:white; border-radius:8px; padding:4px 14px; font-weight:700; font-size:0.85rem; }
</style>

<script>
/* ── Auto-close sidebar on mobile when any sidebar button is clicked ── */
function closeSidebarOnMobile() {
    const mq = window.matchMedia("(max-width: 768px)");
    if (!mq.matches) return;
    const btn = window.parent.document.querySelector('[data-testid="stSidebarCollapseButton"]');
    if (btn) btn.click();
}
/* Attach to every sidebar button click via event delegation */
const observer = new MutationObserver(() => {
    const sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
    if (sidebar && !sidebar._mobileListenerAttached) {
        sidebar.addEventListener('click', (e) => {
            if (e.target.closest('button')) closeSidebarOnMobile();
        });
        sidebar._mobileListenerAttached = true;
    }
});
observer.observe(window.parent.document.body, { childList: true, subtree: true });
</script>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  SESSION STATE BOOTSTRAP
# ─────────────────────────────────────────────
if "logged_in"   not in st.session_state: st.session_state.logged_in   = False
if "username"    not in st.session_state: st.session_state.username     = ""
if "user_name"   not in st.session_state: st.session_state.user_name    = ""
if "auth_tab"    not in st.session_state: st.session_state.auth_tab     = "login"
if "menu_choice" not in st.session_state: st.session_state.menu_choice  = "Home"


# ═══════════════════════════════════════════════
#  AUTH SCREEN  (shown when NOT logged in)
# ═══════════════════════════════════════════════
if not st.session_state.logged_in:

    # ── tab toggle ──
    col_l, col_r = st.columns(2)
    with col_l:
        if st.button("Login",    use_container_width=True):
            st.session_state.auth_tab = "login"
    with col_r:
        if st.button("Register", use_container_width=True):
            st.session_state.auth_tab = "register"

    st.markdown("---")

    # ── LOGIN ──
    if st.session_state.auth_tab == "login":
        st.markdown("<div class='auth-card'><h2> Welcome To Attendify</h2><p>Sign in to your Attendify account</p></div>", unsafe_allow_html=True)
        _, mid, _ = st.columns([1, 2, 1])
        with mid:
            with st.form("login_form"):
                uname = st.text_input("Username")
                pw    = st.text_input("Password", type="password")
                if st.form_submit_button("Login"):
                    result = login_user(uname, pw)
                    if result:
                        st.session_state.logged_in  = True
                        st.session_state.username   = uname.strip().lower()
                        st.session_state.user_name  = result[1]
                        init_user_db(st.session_state.username)
                        st.success(f" Welcome back, {result[1]}!")
                        time.sleep(0.8)
                        st.rerun()
                    else:
                        st.error(" Invalid username or password.")

    # ── REGISTER ──
    else:
        st.markdown("<div class='auth-card'><h2>Create Account </h2><p>Join Attendify – it's free</p></div>", unsafe_allow_html=True)
        _, mid, _ = st.columns([1, 2, 1])
        with mid:
            with st.form("register_form"):
                full_name = st.text_input("Full Name")
                uname     = st.text_input("Username")
                pw        = st.text_input("Password", type="password")
                pw2       = st.text_input("Confirm Password", type="password")
                if st.form_submit_button("Create Account"):
                    if not full_name or not uname or not pw:
                        st.error("All fields are required.")
                    elif pw != pw2:
                        st.error("Passwords do not match.")
                    elif len(pw) < 6:
                        st.error("Password must be at least 6 characters.")
                    else:
                        ok, msg = register_user(uname, pw, full_name)
                        if ok:
                            st.success(msg + " Please log in.")
                            st.session_state.auth_tab = "login"
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(msg)

    st.stop()   # ← nothing below runs until logged in


# ═══════════════════════════════════════════════
#  MAIN APP  (only reached after login)
# ═══════════════════════════════════════════════
USERNAME = st.session_state.username
USER_DISPLAY = st.session_state.user_name

def db():
    """Shorthand: open this user's attendance DB."""
    return get_db_conn(USERNAME)

# ── SIDEBAR ──
with st.sidebar:
    st.markdown(f"<h1 style='text-align:center;color:white;'>Menu</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center;color:rgba(255,255,255,0.6);font-size:0.85rem;'>👤 {USER_DISPLAY}</p>", unsafe_allow_html=True)
    st.markdown("---")
    if st.button("🛖 Home"):            st.session_state.menu_choice = "Home"
    if st.button("➕ Add New Class"):   st.session_state.menu_choice = "Add New Class"
    if st.button("👤 Add Student"):     st.session_state.menu_choice = "Add Student"
    if st.button("📑 Take Attendance"): st.session_state.menu_choice = "Take Attendance"
    if st.button("📔 View Attendance"): st.session_state.menu_choice = "View Attendance"
    if st.button("🗑️ Remove Class"):    st.session_state.menu_choice = "Remove Class"
    st.markdown("---")
    if st.button("🚪 Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

choice    = st.session_state.menu_choice
now       = datetime.now()
today_str = now.strftime("%Y-%m-%d")


# ─────────────────────────────────────────────
#  1. HOME
# ─────────────────────────────────────────────
if choice == "Home":
    conn = db()
    hour = now.hour
    greeting = "Good Morning" if hour < 12 else ("Good Afternoon" if hour < 17 else "Good Evening")
    st.markdown(f"""
        <div class="greeting-box">
            <h1>{greeting}, {USER_DISPLAY}!</h1>
            <p>Today is {now.strftime('%A, %d %B %Y')}</p>
            <h3>Have a Great Day :)</h3>
        </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    classes_today = pd.read_sql(
        f"SELECT COUNT(DISTINCT s.class_id) as count FROM attendance a JOIN students s ON a.student_id=s.id WHERE a.date='{today_str}'",
        conn
    ).iloc[0]['count']
    with col1: st.metric("Total Classes",  len(pd.read_sql("SELECT id FROM classes",  conn)))
    with col2: st.metric("Total Students", len(pd.read_sql("SELECT id FROM students", conn)))
    with col3: st.metric("Attendance Marked (Today)", int(classes_today))
    conn.close()


# ─────────────────────────────────────────────
#  2. ADD NEW CLASS
# ─────────────────────────────────────────────
elif choice == "Add New Class":
    st.header("Class Manager")
    with st.form("main_class_form", clear_on_submit=True):
        dept    = st.text_input("Department").upper()
        branch  = st.text_input("Branch").upper()
        section = st.text_input("Section").upper()
        if st.form_submit_button("Create Class"):
            if dept and branch and section:
                fb, fs = f"{dept} {branch}", section
                conn = db()
                if conn.execute("SELECT id FROM classes WHERE branch=? AND section=?", (fb, fs)).fetchone():
                    st.error("Class already exists!")
                else:
                    conn.execute("INSERT INTO classes (branch, section) VALUES (?, ?)", (fb, fs))
                    conn.commit()
                    st.success(f"{fb} {fs} — Created!")
                    time.sleep(1); st.rerun()
                conn.close()


# ─────────────────────────────────────────────
#  3. ADD STUDENT
# ─────────────────────────────────────────────
elif choice == "Add Student":
    st.header("👤 Add New Student")
    conn = db()
    classes   = conn.execute("SELECT id, branch, section FROM classes").fetchall()
    class_map = {f"{b} {s}": i for i, b, s in classes}

    if class_map:
        opts = list(class_map.keys())
        if 'last_selected_class' not in st.session_state or st.session_state.last_selected_class not in opts:
            st.session_state.last_selected_class = opts[0]
        sel_class = st.selectbox("Assign to Class", opts, index=opts.index(st.session_state.last_selected_class))
        st.session_state.last_selected_class = sel_class

        with st.form("add_student_form", clear_on_submit=True):
            sn = st.text_input("Full Name")
            rn = st.text_input("Registration Number")
            if st.form_submit_button("Save Student"):
                if sn.strip() and rn.strip():
                    cid = class_map[sel_class]
                    if conn.execute("SELECT name FROM students WHERE reg_no=? AND class_id=?", (rn, cid)).fetchone():
                        st.error(f"Reg No {rn} already exists in {sel_class}!")
                    else:
                        conn.execute("INSERT INTO students (class_id, name, reg_no) VALUES (?,?,?)", (cid, sn, rn))
                        conn.commit()
                        st.success(f"{sn} Added!")
                        time.sleep(1); st.rerun()

    st.divider()
    st.subheader("Student Directory")
    for cid, b, s in classes:
        count    = conn.execute("SELECT COUNT(*) FROM students WHERE class_id=?", (cid,)).fetchone()[0]
        students = conn.execute("SELECT id, name, reg_no FROM students WHERE class_id=? ORDER BY CAST(reg_no AS INTEGER) ASC", (cid,)).fetchall()
        with st.expander(f"{b} {s} ({count} students)"):
            for sid, sn, sr in students:
                c1, c2 = st.columns([7, 1])
                c1.write(f"**{sr}** - {sn}")
                if c2.button("❌", key=f"del_{sid}"):
                    conn.execute("DELETE FROM students WHERE id=?", (sid,))
                    conn.commit(); st.rerun()
    conn.close()


# ─────────────────────────────────────────────
#  4. TAKE ATTENDANCE  (fast bulk list mode)
# ─────────────────────────────────────────────
elif choice == "Take Attendance":
    st.header("📑 Take Attendance")
    conn    = db()
    classes = conn.execute("SELECT id, branch, section FROM classes").fetchall()
    class_options = {f"{b} {s}": i for i, b, s in classes}

    if not class_options:
        st.info("No classes found. Add a class first.")
        conn.close()
        st.stop()

    target = st.selectbox("Select Class", list(class_options.keys()))

    # Reset bulk state when class changes
    if st.session_state.get('att_class') != target:
        st.session_state.att_class    = target
        st.session_state.att_statuses = {}
        st.session_state.pop('replace_confirmed', None)

    t_id = class_options[target]

    already_taken = conn.execute(
        "SELECT COUNT(*) FROM attendance "
        "WHERE student_id IN (SELECT id FROM students WHERE class_id=?) AND date=?",
        (t_id, today_str)
    ).fetchone()[0] > 0

    if already_taken and 'replace_confirmed' not in st.session_state:
        st.warning("Attendance has already been taken for today!")
        c1, c2 = st.columns(2)
        if c1.button("Re-Take Attendance"):
            st.session_state.replace_confirmed = True
            st.session_state.att_statuses = {}
            st.rerun()
        if c2.button("Go Back"):
            st.session_state.menu_choice = "Home"; st.rerun()
        conn.close()
        st.stop()

    students = conn.execute(
        "SELECT id, name, reg_no FROM students WHERE class_id=? ORDER BY CAST(reg_no AS INTEGER) ASC",
        (t_id,)
    ).fetchall()

    if not students:
        st.info("No students in this class yet.")
        conn.close()
        st.stop()

    # Init statuses dict  {student_id: "Present"|"Absent"|"OD"|None}
    if 'att_statuses' not in st.session_state:
        st.session_state.att_statuses = {}
    for sid, _, _ in students:
        if sid not in st.session_state.att_statuses:
            st.session_state.att_statuses[sid] = None

    # ── Quick-fill bar ──────────────────────────────────────────────
    st.markdown("##### Quick Fill")
    qc1, qc2, qc3, qc4 = st.columns(4)
    if qc1.button("✅ All Present"):
        for sid, _, _ in students: st.session_state.att_statuses[sid] = "Present"
        st.rerun()
    if qc2.button("❌ All Absent"):
        for sid, _, _ in students: st.session_state.att_statuses[sid] = "Absent"
        st.rerun()
    if qc3.button("🔷 All OD"):
        for sid, _, _ in students: st.session_state.att_statuses[sid] = "OD"
        st.rerun()
    if qc4.button("Reset All"):
        for sid, _, _ in students: st.session_state.att_statuses[sid] = None
        st.rerun()

    st.divider()

    # ── Progress bar ────────────────────────────────────────────────
    marked   = sum(1 for v in st.session_state.att_statuses.values() if v is not None)
    total    = len(students)
    pct      = marked / total if total else 0
    p_count  = sum(1 for v in st.session_state.att_statuses.values() if v == "Present")
    a_count  = sum(1 for v in st.session_state.att_statuses.values() if v == "Absent")
    od_count = sum(1 for v in st.session_state.att_statuses.values() if v == "OD")

    st.progress(pct, text=f"**{marked}/{total} marked** — ✅ {p_count}  ❌ {a_count}  🔷 {od_count}")
    st.markdown("")

    # ── Student rows ────────────────────────────────────────────────
    BADGE = {"Present": "badge-P", "Absent": "badge-A", "OD": "badge-O", None: "badge-N"}
    LABEL = {"Present": "✅ P",    "Absent": "❌ A",    "OD": "🔷 OD",   None: "— ?"}

    for sid, sname, sreg in students:
        cur = st.session_state.att_statuses[sid]
        badge_cls = BADGE[cur]
        badge_lbl = cur if cur else "—"

        col_info, col_p, col_a, col_od = st.columns([5, 1.2, 1.2, 1.2])

        with col_info:
            st.markdown(
                f"<div style='padding:8px 0;'>"
                f"<span style='font-weight:700;font-size:1rem;color:#1a1a2e;'>{sname}</span>"
                f"<span style='font-size:0.82rem;color:#666;margin-left:10px;'>#{sreg}</span>"
                f"&nbsp;&nbsp;<span class='{badge_cls}'>{badge_lbl}</span>"
                f"</div>",
                unsafe_allow_html=True
            )

        if col_p.button( "✅ P",  key=f"p_{sid}",  use_container_width=True):
            st.session_state.att_statuses[sid] = "Present"; st.rerun()
        if col_a.button( "❌ A",  key=f"a_{sid}",  use_container_width=True):
            st.session_state.att_statuses[sid] = "Absent";  st.rerun()
        if col_od.button("🔷 OD", key=f"od_{sid}", use_container_width=True):
            st.session_state.att_statuses[sid] = "OD";      st.rerun()

    st.divider()

    # ── Save button ─────────────────────────────────────────────────
    unmarked = [sname for sid, sname, _ in students if st.session_state.att_statuses[sid] is None]
    if unmarked:
        st.warning(f"⚠️ {len(unmarked)} student(s) not yet marked: {', '.join(unmarked[:5])}{'…' if len(unmarked)>5 else ''}")

    if st.button("Save Attendance", use_container_width=True):
        if unmarked:
            st.error("Please mark all students before saving.")
        else:
            if st.session_state.get('replace_confirmed'):
                conn.execute(
                    "DELETE FROM attendance WHERE date=? AND student_id IN (SELECT id FROM students WHERE class_id=?)",
                    (today_str, t_id)
                )
            for sid, _, _ in students:
                stat = st.session_state.att_statuses[sid]
                conn.execute("INSERT INTO attendance (student_id, status, date) VALUES (?,?,?)", (sid, stat, today_str))
            conn.commit()
            st.session_state.att_statuses = {}
            st.session_state.pop('replace_confirmed', None)
            st.balloons()
            st.success("✅ Attendance saved successfully!")
            time.sleep(1); st.rerun()

    conn.close()


# ─────────────────────────────────────────────
#  5. VIEW ATTENDANCE
# ─────────────────────────────────────────────
elif choice == "View Attendance":
    st.header("History")
    col1, col2, col3 = st.columns([2, 2, 2])
    v_date = col1.date_input("Select Date", now)
    conn   = db()
    classes   = conn.execute("SELECT id, branch, section FROM classes").fetchall()
    class_map = {f"{b} {s}": i for i, b, s in classes}

    if class_map:
        target        = col2.selectbox("Select Class", list(class_map.keys()))
        status_filter = col3.selectbox("Filter Status", ["All", "Present", "Absent", "OD"])

        query  = "SELECT a.id as 'ID', s.reg_no as 'Reg No', s.name as 'Name', a.status as 'Status' FROM attendance a JOIN students s ON a.student_id = s.id WHERE s.class_id = ? AND a.date = ?"
        params = [class_map[target], v_date.strftime("%Y-%m-%d")]
        if status_filter != "All":
            query += " AND a.status = ?"
            params.append(status_filter)
        query += " ORDER BY CAST(s.reg_no AS INTEGER) ASC"
        df = pd.read_sql_query(query, conn, params=params)

        if not df.empty:
            edited_df = st.data_editor(
                df, hide_index=True, use_container_width=True,
                column_config={
                    "ID":     None,
                    "Reg No": st.column_config.TextColumn("Reg No", disabled=True),
                    "Name":   st.column_config.TextColumn("Name",   disabled=True),
                    "Status": st.column_config.SelectboxColumn("Status", options=["Present", "Absent", "OD"], required=True)
                }
            )
            if not df.equals(edited_df):
                if st.button("Save Changes"):
                    diff = edited_df[edited_df['Status'] != df['Status']]
                    for _, row in diff.iterrows():
                        conn.execute("UPDATE attendance SET status=? WHERE id=?", (row['Status'], row['ID']))
                    conn.commit()
                    st.success("Changes saved!")
                    time.sleep(1); st.rerun()

            st.divider()
            st.subheader("📥 Export Options")
            ec1, ec2 = st.columns(2)
            pdf_bytes = create_pdf(edited_df, target, v_date.strftime('%d-%m-%Y'), status_filter)
            ec1.download_button("📄 Download Today's Attendance", data=pdf_bytes,
                                file_name=f"{target}_{v_date}.pdf", mime="application/pdf")

            all_df = pd.read_sql_query(
                "SELECT a.date as 'Date', s.reg_no as 'Reg No', s.name as 'Name', a.status as 'Status' FROM attendance a JOIN students s ON a.student_id=s.id WHERE s.class_id=? ORDER BY a.date DESC, CAST(s.reg_no AS INTEGER) ASC",
                conn, params=[class_map[target]]
            )
            if not all_df.empty:
                all_pdf = create_pdf(all_df, target, "All Time", "All", is_all_time=True)
                ec2.download_button("📄 Export All Time Attendance", data=all_pdf,
                                    file_name=f"{target}_Full_History.pdf", mime="application/pdf")
            else:
                ec2.info("No history to export.")
        else:
            st.info("No records found for this date.")
    conn.close()


# ─────────────────────────────────────────────
#  6. REMOVE CLASS
# ─────────────────────────────────────────────
elif choice == "Remove Class":
    st.header("🗑️ Remove Class")
    conn    = db()
    classes = conn.execute("SELECT id, branch, section FROM classes").fetchall()
    for cid, b, s in classes:
        if st.button(f"Delete {b} {s}", key=f"rm_{cid}"):
            conn.execute("DELETE FROM classes WHERE id=?", (cid,))
            conn.execute("DELETE FROM students WHERE class_id=?", (cid,))
            conn.commit()
            st.error("Deleted!"); time.sleep(1); st.rerun()
    conn.close()
