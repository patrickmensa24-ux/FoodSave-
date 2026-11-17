
from datetime import date

from flask import Flask, render_template, request, redirect, url_for, flash
from database import create_tables, get_connection

app = Flask(__name__)
app.secret_key = "foodsave-development-key"

create_tables()


# HOME PAGE
@app.route("/")
def home():
    connection = get_connection()

    listings = connection.execute("""
        SELECT * FROM food_listings
        ORDER BY created_at DESC
    """).fetchall()

    connection.close()

    return render_template("index.html", listings=listings)


# ADD FOOD DONATION
@app.route("/add-food", methods=["POST"])
def add_food():
    food_name = request.form.get("food_name", "").strip()
    description = request.form.get("description", "").strip()
    quantity_text = request.form.get("quantity", "").strip()
    location = request.form.get("location", "").strip()
    expiry_date = request.form.get("expiry_date", "").strip()
    donor_name = request.form.get("donor_name", "").strip()

    if not all([food_name, quantity_text, location, expiry_date, donor_name]):
        flash("Please complete all required fields.")
        return redirect(url_for("home"))

    try:
        quantity = int(quantity_text)

        if quantity < 1 or quantity > 100000:
            raise ValueError

        date.fromisoformat(expiry_date)

    except ValueError:
        flash("Enter a valid quantity and expiry date.")
        return redirect(url_for("home"))

    connection = get_connection()

    connection.execute("""
        INSERT INTO food_listings
        (food_name, description, quantity, location, expiry_date, donor_name)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (food_name, description, quantity, location, expiry_date, donor_name))

    connection.commit()
    connection.close()

    flash("Food donation added successfully.")
    return redirect(url_for("home"))


# REQUEST FOOD PAGE
@app.route("/request-food/<int:food_id>")
def request_food(food_id):
    connection = get_connection()

    food = connection.execute("""
        SELECT * FROM food_listings
        WHERE id = ? AND status = 'Available'
    """, (food_id,)).fetchone()

    connection.close()

    if food is None:
        flash("This food donation is no longer available.")
        return redirect(url_for("home"))

    return render_template("request_food.html", food=food)


# SUBMIT FOOD REQUEST
@app.route("/submit-request/<int:food_id>", methods=["POST"])
def submit_request(food_id):
    recipient_name = request.form.get("recipient_name", "").strip()
    contact = request.form.get("contact", "").strip()
    requested_quantity_text = request.form.get(
        "requested_quantity", ""
    ).strip()
    message = request.form.get("message", "").strip()

    if not recipient_name or not contact or not requested_quantity_text:
        flash("Please complete all required fields.")
        return redirect(url_for("request_food", food_id=food_id))

    if len(recipient_name) > 100 or len(contact) > 150 or len(message) > 500:
        flash("One or more fields exceed the allowed length.")
        return redirect(url_for("request_food", food_id=food_id))

    try:
        requested_quantity = int(requested_quantity_text)

        if requested_quantity < 1:
            raise ValueError

    except ValueError:
        flash("Requested quantity must be a positive whole number.")
        return redirect(url_for("request_food", food_id=food_id))

    connection = get_connection()

    food = connection.execute("""
        SELECT * FROM food_listings
        WHERE id = ? AND status = 'Available'
    """, (food_id,)).fetchone()

    if food is None:
        connection.close()
        flash("This food donation is no longer available.")
        return redirect(url_for("home"))

    if requested_quantity > food["quantity"]:
        connection.close()
        flash("Requested quantity exceeds the available amount.")
        return redirect(url_for("request_food", food_id=food_id))

    connection.execute("""
        INSERT INTO food_requests
        (food_id, recipient_name, contact, requested_quantity, message)
        VALUES (?, ?, ?, ?, ?)
    """, (food_id, recipient_name, contact, requested_quantity, message))

    connection.commit()
    connection.close()

    flash("Your food request has been submitted.")
    return redirect(url_for("home"))


# DASHBOARD
@app.route("/dashboard")
def dashboard():
    connection = get_connection()

    stats = connection.execute("""
        SELECT
            COUNT(*) AS total_donations,
            COALESCE(SUM(
                CASE WHEN status = 'Available' THEN quantity ELSE 0 END
            ), 0) AS available_food
        FROM food_listings
    """).fetchone()

    request_stats = connection.execute("""
        SELECT
            SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END)
                AS pending_requests,
            SUM(CASE WHEN status = 'Approved' THEN 1 ELSE 0 END)
                AS approved_requests
        FROM food_requests
    """).fetchone()

    connection.close()

    return render_template(
        "dashboard.html",
        stats=stats,
        request_stats=request_stats
    )


# MANAGE FOOD DONATIONS
@app.route("/manage-donations")
def manage_donations():
    connection = get_connection()

    listings = connection.execute("""
        SELECT *
        FROM food_listings
        ORDER BY created_at DESC
    """).fetchall()

    connection.close()

    return render_template(
        "manage_donations.html",
        listings=listings
    )


# MANAGE FOOD REQUESTS
@app.route("/manage-requests")
def manage_requests():
    connection = get_connection()

    requests = connection.execute("""
        SELECT
            food_requests.*,
            food_listings.food_name,
            food_listings.quantity
        FROM food_requests
        JOIN food_listings
        ON food_requests.food_id = food_listings.id
        ORDER BY food_requests.created_at DESC
    """).fetchall()

    connection.close()

    return render_template(
        "manage_requests.html",
        requests=requests
    )


# APPROVE OR REJECT A FOOD REQUEST
@app.route("/update-request/<int:request_id>", methods=["POST"])
def update_request(request_id):
    status = request.form.get("status")

    if status not in ["Approved", "Rejected"]:
        flash("Invalid request status.")
        return redirect(url_for("manage_requests"))

    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")

        food_request = connection.execute("""
            SELECT *
            FROM food_requests
            WHERE id = ?
        """, (request_id,)).fetchone()

        if food_request is None:
            connection.rollback()
            flash("Request not found.")
            return redirect(url_for("manage_requests"))

        if food_request["status"] != "Pending":
            connection.rollback()
            flash("This request has already been processed.")
            return redirect(url_for("manage_requests"))

        if status == "Approved":
            food = connection.execute("""
                SELECT *
                FROM food_listings
                WHERE id = ?
            """, (food_request["food_id"],)).fetchone()

            if food is None or food["status"] != "Available":
                connection.rollback()
                flash("This donation is no longer available.")
                return redirect(url_for("manage_requests"))

            requested_quantity = food_request["requested_quantity"]

            if requested_quantity > food["quantity"]:
                connection.rollback()
                flash("Not enough food remains to approve this request.")
                return redirect(url_for("manage_requests"))

            remaining_quantity = food["quantity"] - requested_quantity

            new_food_status = (
                "Available" if remaining_quantity > 0 else "Unavailable"
            )

            connection.execute("""
                UPDATE food_listings
                SET quantity = ?, status = ?
                WHERE id = ?
            """, (remaining_quantity, new_food_status, food_request["food_id"]))

        connection.execute("""
            UPDATE food_requests
            SET status = ?
            WHERE id = ?
        """, (status, request_id))

        connection.commit()
        flash(f"Request {status.lower()} successfully.")

    except Exception:
        connection.rollback()
        flash("Something went wrong while processing the request.")

    finally:
        connection.close()

    return redirect(url_for("manage_requests"))


# DELETE A FOOD DONATION
@app.route("/delete-donation/<int:food_id>", methods=["POST"])
def delete_donation(food_id):
    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")

        food = connection.execute("""
            SELECT id FROM food_listings
            WHERE id = ?
        """, (food_id,)).fetchone()

        if food is None:
            connection.rollback()
            flash("Donation not found.")
            return redirect(url_for("manage_donations"))

        connection.execute("""
            DELETE FROM food_requests
            WHERE food_id = ?
        """, (food_id,))

        connection.execute("""
            DELETE FROM food_listings
            WHERE id = ?
        """, (food_id,))

        connection.commit()
        flash("Food donation deleted successfully.")

    except Exception:
        connection.rollback()
        flash("Could not delete this donation.")

    finally:
        connection.close()

    return redirect(url_for("manage_donations"))


if __name__ == "__main__":
    app.run(debug=True)
