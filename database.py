import sqlite3

DATABASE_NAME = "foodsave.db"


def get_connection():
    """Connect to the FoodSave database."""
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_tables():
    """Create the donation and food request tables."""
    connection = get_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS food_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_name TEXT NOT NULL,
            description TEXT,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            location TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            donor_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Available',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS food_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_id INTEGER NOT NULL,
            recipient_name TEXT NOT NULL,
            contact TEXT NOT NULL,
            requested_quantity INTEGER NOT NULL CHECK (requested_quantity > 0),
            message TEXT,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (food_id) REFERENCES food_listings(id)
        )
    """)

    connection.commit()
    connection.close()


if __name__ == "__main__":
    create_tables()
    print("FoodSave database tables are ready.")