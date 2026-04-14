import sys
import socket
import threading
import time
import json
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QSpinBox, QMessageBox
)
from PySide6.QtCore import Qt, QTimer

APP_NAME = "AB Server Health Checker"
DATA_FILE = Path("servers_data.json")  # Persistent storage

# ------------------------
# Server Entry
# ------------------------
class ServerEntry:
    def __init__(self, server_id, ip, port, status="UNKNOWN", last_checked=0):
        self.server_id = server_id
        self.ip = ip
        self.port = int(port)
        self.status = status
        self.last_checked = last_checked

    def to_dict(self):
        return {"server_id": self.server_id, "ip": self.ip, "port": self.port}

    @staticmethod
    def from_dict(d):
        return ServerEntry(d["server_id"], d["ip"], d["port"])

# ------------------------
# Port Checking
# ------------------------
def check_port(entry, timeout=0.5):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((entry.ip, entry.port))
        entry.status = "ACTIVE"
    except:
        entry.status = "DEAD"
    finally:
        entry.last_checked = time.time()
        try:
            s.close()
        except:
            pass

# ------------------------
# Main App
# ------------------------
class ABServerHealthChecker(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(850, 500)
        self.servers = []
        self.auto_refresh = False

        self.load_servers()
        self.init_ui()

    # ------------------------
    # UI
    # ------------------------
    def init_ui(self):
        layout = QVBoxLayout()

        # ---------- Add Server Frame ----------
        add_frame = QHBoxLayout()
        self.id_input = QLineEdit(); self.id_input.setPlaceholderText("Server ID")
        self.ip_input = QLineEdit(); self.ip_input.setPlaceholderText("IP / Hostname")
        self.port_input = QLineEdit(); self.port_input.setPlaceholderText("Port")
        add_btn = QPushButton("Add Server"); add_btn.clicked.connect(self.add_server)
        remove_btn = QPushButton("Remove Selected"); remove_btn.clicked.connect(self.remove_selected)

        add_frame.addWidget(QLabel("ID:")); add_frame.addWidget(self.id_input)
        add_frame.addWidget(QLabel("IP:")); add_frame.addWidget(self.ip_input)
        add_frame.addWidget(QLabel("Port:")); add_frame.addWidget(self.port_input)
        add_frame.addWidget(add_btn); add_frame.addWidget(remove_btn)
        layout.addLayout(add_frame)

        # ---------- Auto-refresh Frame ----------
        auto_frame = QHBoxLayout()
        auto_frame.addWidget(QLabel("Auto Refresh Interval (sec):"))
        self.interval_spin = QSpinBox(); self.interval_spin.setRange(1, 3600); self.interval_spin.setValue(5)
        auto_frame.addWidget(self.interval_spin)
        start_btn = QPushButton("Start Auto"); start_btn.clicked.connect(self.start_auto)
        stop_btn = QPushButton("Stop Auto"); stop_btn.clicked.connect(self.stop_auto)
        auto_frame.addWidget(start_btn); auto_frame.addWidget(stop_btn)
        layout.addLayout(auto_frame)

        # ---------- Table ----------
        self.table = QTableWidget(0,5)
        self.table.setHorizontalHeaderLabels(["ID","IP","Port","Status","Last Checked"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.setLayout(layout)
        self.refresh_table()

        # ---------- Timer ----------
        self.timer = QTimer(); self.timer.timeout.connect(self.auto_refresh_check)

        # ---------- Modern Styles (QSS) ----------
        self.setStyleSheet("""
        QWidget{background:#1e1e2f;color:#ffffff;font-family:Segoe UI;}
        QLineEdit{background:#2e2e3e;color:white;padding:4px;border-radius:4px;border:1px solid #555;}
        QPushButton{background:#3a3a5a;color:white;padding:5px 12px;border:none;border-radius:5px;}
        QPushButton:hover{background:#505070;}
        QTableWidget{background:#2e2e3e;color:white;border:1px solid #444;}
        QHeaderView::section{background:#3a3a5a;color:white;padding:4px;border:none;}
        """)

    # ------------------------
    # CRUD
    # ------------------------
    def add_server(self):
        sid = self.id_input.text().strip(); ip = self.ip_input.text().strip(); port_text = self.port_input.text().strip()
        if not sid or not ip or not port_text:
            QMessageBox.warning(self,"Input Error","ID, IP and Port are required")
            return
        try: port = int(port_text); assert 1<=port<=65535
        except: QMessageBox.warning(self,"Input Error","Port must be 1-65535"); return
        for s in self.servers:
            if s.server_id==sid:
                QMessageBox.warning(self,"Duplicate",f"Server ID {sid} exists")
                return
        entry = ServerEntry(sid, ip, port)
        self.servers.append(entry)
        self.save_servers()
        self.refresh_table()
        self.id_input.clear(); self.ip_input.clear(); self.port_input.clear()

    def remove_selected(self):
        selected_rows = set([i.row() for i in self.table.selectedItems()])
        if not selected_rows: QMessageBox.information(self,"Remove","Select at least one row"); return
        ids_to_remove = [self.table.item(r,0).text() for r in selected_rows]
        self.servers = [s for s in self.servers if s.server_id not in ids_to_remove]
        self.save_servers()
        self.refresh_table()

    # ------------------------
    # Refresh
    # ------------------------
    def manual_refresh(self):
        threading.Thread(target=self.check_all_servers, daemon=True).start()

    def start_auto(self):
        self.auto_refresh = True
        self.timer.start(int(self.interval_spin.value())*1000)
        QMessageBox.information(self,"Auto","Auto refresh started")

    def stop_auto(self):
        self.auto_refresh = False
        self.timer.stop()
        QMessageBox.information(self,"Auto","Auto refresh stopped")

    def auto_refresh_check(self):
        if self.auto_refresh: self.manual_refresh()

    def check_all_servers(self):
        threads=[]
        for s in self.servers:
            t=threading.Thread(target=check_port,args=(s,))
            t.start(); threads.append(t)
        for t in threads: t.join()
        self.refresh_table()

    # ------------------------
    # Table Update
    # ------------------------
    def refresh_table(self):
        self.table.setRowCount(0)
        for s in self.servers:
            last = "-" if s.last_checked==0 else f"{int(time.time()-s.last_checked)}s ago"
            row = self.table.rowCount(); self.table.insertRow(row)
            self.table.setItem(row,0,QTableWidgetItem(s.server_id))
            self.table.setItem(row,1,QTableWidgetItem(s.ip))
            self.table.setItem(row,2,QTableWidgetItem(str(s.port)))
            status_item = QTableWidgetItem(s.status)
            status_item.setForeground(Qt.green if s.status=="ACTIVE" else Qt.red)
            self.table.setItem(row,3,status_item)
            self.table.setItem(row,4,QTableWidgetItem(last))

    # ------------------------
    # Persistent Storage
    # ------------------------
    def save_servers(self):
        data = [s.to_dict() for s in self.servers]
        with open(DATA_FILE,"w") as f: json.dump(data,f,indent=2)

    def load_servers(self):
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE,"r") as f:
                    data = json.load(f)
                self.servers = [ServerEntry.from_dict(d) for d in data]
            except: self.servers=[]

# ------------------------
# Run App
# ------------------------
if __name__=="__main__":
    app = QApplication(sys.argv)
    window = ABServerHealthChecker()
    window.show()
    sys.exit(app.exec())
