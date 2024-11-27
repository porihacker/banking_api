from flask import (
    Flask,
    render_template,
    session,
    redirect,
    request,
    url_for,
    flash,
    jsonify,
)
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


# testing


class Accounts(db.Model):
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), nullable=False)
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
    # if "user" in session:
    #     # Redirect to accounts page if user is logged in
    #     return redirect(url_for("accounts"))

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            session["user"] = user["email"]
            return redirect(url_for("accounts"))
        except Exception as e:
            flash(f"Failed to login: {str(e)}")
            return redirect(url_for("home"))
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
            session["user"] = user["email"]

            id_token = session.get("user")
            if not id_token:
                return redirect(url_for("login"))

            new_user = Users(
                user_id=session["user"], name=name, surname=surname, email=email
            )
            db.session.add(new_user)
            db.session.commit()

            return redirect("/accounts")
        except Exception as e:
            return f"There was an error while signing you up, please try again: {e}"

    return render_template("signup.html")


@app.route("/logout", methods=["POST"])
def logout():
    try:
        session.pop("user")
        return redirect("/")
    except:
        return "Failed to logout"


@app.route("/accounts")
def accounts():
    # Check if user is logged in
    if "user" not in session:
        flash("Please log in to access your accounts")
        return redirect(url_for("home"))  # Changed from login to home

    try:
        # Retrieve user details
        user_detail = Users.query.filter_by(email=session["user"]).first()

        if not user_detail:
            flash("User not found. Please log in again.")
            return redirect(url_for("home"))

        # Fetch user's accounts
        user_accounts = Accounts.query.filter_by(user_id=session["user"]).all()

        # Render template with both user and accounts
        return render_template(
            "accounts.html",
            user=user_detail,
            accounts=user_accounts,
        )

    except Exception as e:
        # Print error for debugging
        print(f"Error in accounts route: {str(e)}")
        flash("An error occurred. Please try again.")
        return redirect(url_for("home"))


@app.route("/create_acc", methods=["GET", "POST"])
def create_acc():
    id_token = session.get("user")
    if not id_token:
        return redirect(url_for("login"))

    # user = Users.query.filter_by(user_id=id_token).first()
    # if not user:
    #     flash("user not found!")
    #     return redirect(url_for('logout'))

    if request.method == "POST":
        acc_name = request.form.get("acc_name")
        balance = request.form.get("balance", type=int) or 0
        print(" Starting  creating accout....")

        new_acc = Accounts(user_id=id_token, account_name=acc_name, balance=balance)
        try:
            print(" Am here creating accout")
            db.session.add(new_acc)
            db.session.commit()
            flash(f"Account '{acc_name}' created successfully!", "success")
            return redirect("/accounts")
        except Exception as error:
            flash(f"Error creating account: {error}")
            return redirect("/create_acc")

    return render_template("create_acc.html")

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
        return render_template("delete_account.html", account=account)

    if request.method == "POST":
        try:
            db.session.delete(account)
            db.session.commit()
            flash("Account deleted successfully.", "success")
        except Exception as e:
            flash(f"Failed to delete account: {e}", "error")
        return redirect(url_for("accounts"))


@app.route("/accounts/<int:account_id>/transactions", methods=["GET"])
def account_transactions(account_id):
    id_token = session.get("user")
    if not id_token:

        return redirect(url_for("login"))

    account = Accounts.query.filter_by(id=account_id).first()

    if not account:

        return jsonify({"error": "Account not found"}), 404

    transactions = Transactions.query.filter_by(account_id=account_id).all()

    return render_template(
        "transactions.html", account=account, transactions=transactions
    )


@app.route("/accounts/<account_id>/transactions/transact", methods=["POST", "GET"])
def transact(account_id):
    id_token = session.get("user")
    if not id_token:
        return redirect(url_for("login"))

    account = Accounts.query.filter_by(id=account_id).first()
    if not account:
        return jsonify({"error": "Account not found"}), 404
    current_bal = int(account.balance)
    transaction_type = request.form.get("transaction")
    amount = request.form.get("amount")

    if request.method == "POST":
        if transaction_type == "withdrawal":
            if int(amount) > current_bal:
                flash("You have insufficient funds to make this transaction.", "error")
            else:
                current_bal -= int(amount)
                account.balance = current_bal
                transaction = Transactions(
                    account_id=account_id,
                    transaction_type=transaction_type,
                    amount=amount,
                    balance=current_bal,
                )
                try:
                    db.session.add(transaction)
                    db.session.commit()
                    flash("Transaction successfull.", "success")
                except Exception as e:
                    flash(f"Failed to make transaction. Please try again: {e}", "error")
        else:
            current_bal += int(amount)
            account.balance = current_bal
            transaction = Transactions(
                account_id=account_id,
                transaction_type=transaction_type,
                amount=amount,
                balance=current_bal,
            )
            try:
                db.session.add(transaction)
                db.session.commit()
                flash("Transaction successfull.", "success")
            except Exception as e:
                flash(f"Failed to make transaction. Please try again: {e}", "error")

        return redirect(url_for("account_transactions", account_id=account_id))

    else:
        return render_template(
            "transact.html", account=account, current_bal=current_bal
        )


@app.route("/update/<int:account_id>", methods=["GET", "POST"])
def update_account(account_id):
    if "user" not in session:
        return redirect(url_for("home"))

    account = Accounts.query.get_or_404(account_id)

    # Verify the account belongs to the logged-in user
    if account.user_id != session["user"]:
        flash("You don't have permission to edit this account", "error")
        return redirect(url_for("accounts"))

    if request.method == "POST":
        try:
            account.account_name = request.form.get("account_name")
            db.session.commit()
            flash("Account updated successfully!", "success")
            return redirect(url_for("accounts"))
        except Exception as e:
            flash(f"Error updating account: {e}", "error")
            return redirect(url_for("update_account", account_id=account_id))

    return render_template("update.html", account=account)


if __name__ == "__main__":
    app.run(debug=True)
