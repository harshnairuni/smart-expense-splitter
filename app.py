import sqlite3
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

DATABASE = "database.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            group_id INTEGER,
            FOREIGN KEY (group_id) REFERENCES groups (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            paid_by INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            FOREIGN KEY (paid_by) REFERENCES members (id),
            FOREIGN KEY (group_id) REFERENCES groups (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expense_shares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_id INTEGER NOT NULL,
            member_id INTEGER NOT NULL,
            share_amount REAL NOT NULL,
            FOREIGN KEY (expense_id) REFERENCES expenses (id),
            FOREIGN KEY (member_id) REFERENCES members (id)
        )
    """)

    conn.commit()
    conn.close()

def simplify_settlements(balances):
    creditors = []
    debtors = []

    for person in balances:
        if person["balance"] > 0:
            creditors.append({
                "name": person["name"],
                "amount": person["balance"]
            })
        elif person["balance"] < 0:
            debtors.append({
                "name": person["name"],
                "amount": -person["balance"]
            })

    settlements = []

    i = 0
    j = 0

    while i < len(debtors) and j < len(creditors):
        debtor = debtors[i]
        creditor = creditors[j]

        amount = min(debtor["amount"], creditor["amount"])

        settlements.append({
            "from": debtor["name"],
            "to": creditor["name"],
            "amount": round(amount, 2)
        })

        debtor["amount"] -= amount
        creditor["amount"] -= amount

        if debtor["amount"] == 0:
            i += 1
        if creditor["amount"] == 0:
            j += 1

    return settlements

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/add-group", methods=["GET", "POST"])
def add_group():
    if request.method == "POST":
        group_name = request.form["group_name"]

        conn = get_db_connection()
        conn.execute("INSERT INTO groups (name) VALUES (?)", (group_name,))
        conn.commit()
        conn.close()

        return redirect(url_for("home"))

    return render_template("add_group.html")

@app.route("/add-member", methods=["GET", "POST"])
def add_member():
    conn = get_db_connection()
    groups = conn.execute("SELECT * FROM groups").fetchall()

    if request.method == "POST":
        member_name = request.form["member_name"]
        group_id = request.form["group_id"]

        conn.execute(
            "INSERT INTO members (name, group_id) VALUES (?, ?)",
            (member_name, group_id)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("home"))

    conn.close()
    return render_template("add_member.html", groups=groups)

@app.route("/add-expense", methods=["GET", "POST"])
def add_expense():
    conn = get_db_connection()
    groups = conn.execute("SELECT * FROM groups").fetchall()
    members = conn.execute("SELECT * FROM members").fetchall()

    if request.method == "POST":
        description = request.form["description"]
        amount = float(request.form["amount"])
        paid_by = int(request.form["paid_by"])
        group_id = int(request.form["group_id"])
        participants = request.form.getlist("participants")

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO expenses (description, amount, paid_by, group_id) VALUES (?, ?, ?, ?)",
            (description, amount, paid_by, group_id)
        )
        expense_id = cursor.lastrowid

        split_count = len(participants)
        if split_count > 0:
            share = amount / split_count
            for member_id in participants:
                cursor.execute(
                    "INSERT INTO expense_shares (expense_id, member_id, share_amount) VALUES (?, ?, ?)",
                    (expense_id, int(member_id), share)
                )

        conn.commit()
        conn.close()

        return redirect(url_for("home"))

    conn.close()
    return render_template("add_expense.html", groups=groups, members=members)

@app.route("/balances")
def balances():
    conn = get_db_connection()

    members = conn.execute("SELECT * FROM members").fetchall()
    expenses = conn.execute("SELECT * FROM expenses").fetchall()
    shares = conn.execute("SELECT * FROM expense_shares").fetchall()

    paid = {member["id"]: 0 for member in members}
    owes = {member["id"]: 0 for member in members}
    names = {member["id"]: member["name"] for member in members}

    for expense in expenses:
        paid[expense["paid_by"]] += expense["amount"]

    for share in shares:
        owes[share["member_id"]] += share["share_amount"]

    balances_list = []
    for member in members:
        member_id = member["id"]
        net_balance = paid[member_id] - owes[member_id]
        balances_list.append({
            "name": names[member_id],
            "paid": round(paid[member_id], 2),
            "owes": round(owes[member_id], 2),
            "balance": round(net_balance, 2)
        })

    settlements = simplify_settlements(balances_list)

    conn.close()
    return render_template("balances.html", balances=balances_list, settlements=settlements)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)