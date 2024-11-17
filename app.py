from flask import Flask, render_template, session, redirect, request, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
import pyrebase
import firebase_admin
from firebase_admin import credentials
import os
from datetime import datetime

app = Flask(__name__)
config = {
    "apiKey": os.environ.get("API_KEY"),
    "authDomain": os.environ.get("AUTH_DOMAIN"),
    "projectId": os.environ.get("PROJECT_ID"),
    "storageBucket": os.environ.get("STORAGE_BUCKET"),
    "messagingSenderId": os.environ.get("MESSAGING_SENDER_ID"),
    "appId": os.environ.get("APP_ID"),
    "measurementId": os.environ.get("MEASUREMENT_ID"),
    "databaseURL": "",
}

firebase = pyrebase.initialize_app(config)
auth = firebase.auth()

app.secret_key = os.environ.get("BANK_KEY")

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///bank.db"
db = SQLAlchemy(app)


class Users(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    surname = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f"<User {self.id}>"


class Accounts(db.Model):
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    account_name = db.Column(db.String(100), nullable=False)
    balance = db.Column(db.Integer, nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Account {self.id}>"


class Transactions(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    transaction_type = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    balance = db.Column(db.Integer, nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Transaction {self.id}>"


cred = credentials.Certificate("firebase-adminsdk.json")
firebase_admin.initialize_app(cred)


@app.route("/", methods=["POST", "GET"])
def home():
    if "user" in session:
        return render_template("accounts.html")
    
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            session["user"] = user["idToken"]
            return redirect("/accounts")
        except Exception as e:
            return f"Failed to login: {e}"
    return render_template("index.html")


@app.route("/signup", methods=["POST", "GET"])
def signup():
    if request.method == "POST":
        name = request.form.get("name")
        surname = request.form.get("surname")
        email = request.form.get("email")
        password = request.form.get("password")
    
        existing_user = Users.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already exists in our system", "error")
            return redirect("/")
        
        try:
            user = auth.create_user_with_email_and_password(email, password)
            session["user"] = user["idToken"]

            id_token = session.get("user")
            if not id_token:
               return redirect(url_for("login"))
            
            new_user = Users(user_id=session['user'], name=name, surname=surname, email=email)
            db.session.add(new_user)
            db.session.commit()
            
            return redirect("/accounts")
        except Exception as e:
            return f"There was an error while signing you up, please try again: {e}"

    return render_template("signup.html")


@app.route("/logout", methods=["POST"])
def logout():
    try:
        session.pop("user", None)
        return redirect("/")
    except:
        flash("Failed to logout")
        return redirect('/')


@app.route("/accounts")
def accounts():
    id_token = session.get("user")
    if not id_token:
        return redirect(url_for("login"))

    user = Users.query.filter_by(user_id=id_token).first()
    if not user:
        flash("user not found!")
        return redirect(url_for('logout'))
    
    user_account = Accounts.query.filter_by(user_id=user.id).order_by(
        Accounts.date_created, Accounts.balance
    ).all()
    return render_template("accounts.html", accounts=user_account)


@app.route("/create_acc", methods=["GET", "POST"])
def create_acc():
    id_token = session.get("user")
    if not id_token:
        return redirect(url_for("login"))
    
    user = Users.query.filter_by(user_id=id_token).first()
    if not user:
        flash("user not found!")
        return redirect(url_for('logout'))
    
    if request.method == "POST":
        acc_name = request.form.get("acc_name")
        balance = request.form.get("initial_balance", type=int) or 0

        new_acc = Accounts(user_id=user.id, account_name=acc_name, balance=balance)
        try:
            db.session.add(new_acc)
            db.session.commit()
            flash(f"Account '{acc_name}' created successfully!", "success")
            return redirect("/accounts")
        except Exception as error:
            flash(f"Error creating account: {error}")
            return redirect("/create_acc")
        
    return render_template("create_acc.html")


@app.route("/transactions/transact", methods=["POST", "GET"])
def transact():
    id_token = session.get("user")
    if not id_token:
        return redirect(url_for("login"))
    # if request.method == "POST":
    #     transaction_type = request.form.get("transaction")
    #     amount = request.form.get("amount")
    # try:
    #     # balance = Accounts.query.where(Accounts.user_id == id_token).first()
    #     # new_user = Users(
    #     #     account_id=account_id,transaction_type=transaction_type,amount=amount
    #     #     )
    #     # db.session.add(new_user)
    #     # db.session.commit()
    #     # return redirect("/transactions")
    # except Exception as e:
    #     return f"There was an error while signing you up, please try again: {e}"

    return render_template("transact.html")


@app.route("/delete_account/<int:id>", methods=["POST", "GET"])
def delete_account(id):
    if "user" not in session:
        return redirect(url_for("home"))

    account = Accounts.query.get(id)
    if not account:
        flash("Account not found.", "error")
        return redirect(url_for("home"))

    if request.method == "GET":
        flash("Are you sure you want to delete your account?", "warning")
        return render_template("confirm_delete_account.html", account=account)

    if request.method == "POST":
        try:
            db.session.delete(account)
            db.session.commit()
            flash("Account deleted successfully.", "success")
        except Exception as e:
            flash(f"Failed to delete account: {e}", "error")
        return redirect(url_for("home"))


@app.route("/accounts/<int:account_id>/transactions", methods=["GET"])
def account_transactions(account_id):
    id_token = session.get("user")
    if not id_token:

        return redirect(url_for("login"))

    account = Accounts.query.filter_by(id=account_id).first()

    if not account:

        return jsonify({"error": "Account not found"}), 404

    transactions = Transactions.query.filter_by(account_id=account_id).all()

    return render_template("balance.html", account=account, transactions=transactions)


if __name__ == "__main__":
    app.run(debug=True)
