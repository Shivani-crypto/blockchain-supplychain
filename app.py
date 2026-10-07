import os
import time
import datetime
import werkzeug.security
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify

from blockchain import BlockchainInterface
from ipfs_aes import generate_or_load_aes_key, encrypt_data, decrypt_data, upload_to_ipfs_or_pinata, get_from_ipfs
from email_service import send_email_alert, get_in_app_notifications
from disruption_engine import DisruptionEngine

app = Flask(__name__)
app.secret_key = os.urandom(24)

# ==========================================
# CONFIGURATION (PINATA / SMTP / BLOCKCHAIN)
# ==========================================
GANACHE_URL = "http://127.0.0.1:8545"

# Pinata IPFS Keys (Configure if available)
PINATA_API_KEY = os.environ.get("PINATA_API_KEY", "26063c915add365344fd")
PINATA_SECRET_KEY = os.environ.get("PINATA_SECRET_KEY", "4073d4d7f67b3df7cbce6e66fa36f19b78a6efc1b3ca6bb1ec4b3faea128ef3a")

# SMTP Configuration (Configure if using real SMTP server)
SMTP_CONFIG = {
    "server": os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
    "port": int(os.environ.get("SMTP_PORT", 587)),
    "username": os.environ.get("SMTP_USER", "client3105.tech@gmail.com"),
    "password": os.environ.get("SMTP_PASS", "etbddqbqcdepwnli"),
    "sender_email": os.environ.get("SMTP_SENDER", "client3105.tech@gmail.com")
}

# ==========================================
# INITIALIZATION
# ==========================================
# 1. AES Key setup
aes_key = generate_or_load_aes_key()

# 2. Connect Web3 & Blockchain Interface
bc = BlockchainInterface(rpc_url=GANACHE_URL, contract_address="0x5c2dEC3Fb2CB5613517f70DcFAc38598CB4B4637")

# 3. Initialize Disruption Engine
disruption_engine = DisruptionEngine(bc)

# Local password database (In production, stored in database or hash on chain)
USER_PASSWORDS = {
    "admin": werkzeug.security.generate_password_hash("admin"),
    "AdminUser": werkzeug.security.generate_password_hash("admin"),
    "ApexMaterials": werkzeug.security.generate_password_hash("supplier123"),
    "GlobalTechSupplies": werkzeug.security.generate_password_hash("supplier123"),
    "OmniMfgCorp": werkzeug.security.generate_password_hash("mfg123"),
    "ExpressDistributors": werkzeug.security.generate_password_hash("dist123"),
    "MetroRetailStore": werkzeug.security.generate_password_hash("retailer123"),
    "JohnConsumer": werkzeug.security.generate_password_hash("consumer123")
}

def initialize_sample_data():
    """Seed initial prototype demo data on blockchain if chain is empty."""
    try:
        accounts = bc.w3.eth.accounts
        if len(accounts) < 6:
            print("[Init Warning] Not enough Ethereum accounts on network for full role seeding.")
            return

        participants = bc.get_all_participants()
        if len(participants) <= 1:
            print("[Init] Seeding default prototype accounts and roles on Blockchain...")
            
            # Admin (account 0)
            bc.register_user_on_chain("admin", "admin@supplychain.eth", "ADMIN", accounts[0])
            
            # Supplier (account 1)
            bc.register_user_on_chain("ApexMaterials", "supplier@apex.com", "SUPPLIER", accounts[1])
            bc.approve_user(accounts[1], accounts[0])

            # Alternate Supplier (account 2)
            bc.register_user_on_chain("GlobalTechSupplies", "supplier2@global.com", "SUPPLIER", accounts[2])
            bc.approve_user(accounts[2], accounts[0])

            # Manufacturer (account 3)
            bc.register_user_on_chain("OmniMfgCorp", "mfg@omni.com", "MANUFACTURER", accounts[3])
            bc.approve_user(accounts[3], accounts[0])

            # Distributor (account 4)
            bc.register_user_on_chain("ExpressDistributors", "dist@express.com", "DISTRIBUTOR", accounts[4])
            bc.approve_user(accounts[4], accounts[0])

            # Retailer (account 5)
            bc.register_user_on_chain("MetroRetailStore", "retailer@metro.com", "RETAILER", accounts[5])
            bc.approve_user(accounts[5], accounts[0])

            # Consumer (account 6 if available else account 0)
            consumer_acc = accounts[6] if len(accounts) > 6 else accounts[0]
            bc.register_user_on_chain("JohnConsumer", "consumer@gmail.com", "CONSUMER", consumer_acc)
            bc.approve_user(consumer_acc, accounts[0])

            # Seed Sample Material
            bc.save_material("MAT-101", "High-Grade Semiconductor Silicon", "Electronics", 1500, 2, "QmSampleIpfsHash101", accounts[1])
            bc.save_material("MAT-102", "Industrial Aluminum Casing", "Metals", 800, 4, "QmSampleIpfsHash102", accounts[2])

            # Seed Sample Product
            bc.save_product("PROD-8001", "Quantum X1 Smart Processor", "Consumer Tech", 1499, ["MAT-101"], accounts[3])

            print("[Init] Default demo data seeded successfully!")
    except Exception as e:
        print(f"[Init Error] Seeding sample data failed: {e}")

# Run initial seeding
initialize_sample_data()

# ==========================================
# ROUTES
# ==========================================

@app.route("/")
def index():
    counts = bc.get_system_counts()
    return render_template("index.html", contract_address=bc.contract_address or "Not Deployed", system_counts=counts)

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        participants = bc.get_all_participants()
        matched = None
        for p in participants:
            if (p["username"].lower() == username.lower() or p["username"].lower() == "admin" or p["username"].lower() == "adminuser") and p["role_str"] == "ADMIN":
                matched = p
                break

        if not matched and (username.lower() == "admin" or username.lower() == "adminuser"):
            admin_acc = bc.w3.eth.accounts[0]
            matched = {
                "username": username,
                "role_str": "ADMIN",
                "ethAddress": admin_acc,
                "email": "admin@supplychain.eth",
                "status_str": "APPROVED"
            }

        if matched:
            stored_hash = USER_PASSWORDS.get(username) or USER_PASSWORDS.get("admin") or USER_PASSWORDS.get("AdminUser")
            if stored_hash and not werkzeug.security.check_password_hash(stored_hash, password) and password != "admin":
                flash("Invalid Admin password.", "error")
                return redirect(url_for("admin_login"))

            # Set Session
            session["username"] = matched["username"]
            session["role"] = "ADMIN"
            session["eth_address"] = matched["ethAddress"]
            session["email"] = matched.get("email", "admin@supplychain.eth")

            flash("Welcome back, Admin! Logged into System Governance Portal.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Admin credentials not recognized.", "error")
            return redirect(url_for("admin_login"))

    return render_template("admin_login.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "").upper()

        if role == "ADMIN":
            flash("Please use the dedicated Admin Login portal.", "info")
            return redirect(url_for("admin_login"))

        participants = bc.get_all_participants()
        matched = None
        for p in participants:
            if p["username"].lower() == username.lower() and p["role_str"] == role:
                matched = p
                break

        if matched:
            if matched["status_str"] != "APPROVED":
                flash(f"Account registration status is {matched['status_str']}. Please wait for Admin approval.", "warning")
                return redirect(url_for("login"))

            # Password check (or prototype default pass)
            stored_hash = USER_PASSWORDS.get(username)
            if stored_hash and not werkzeug.security.check_password_hash(stored_hash, password):
                flash("Invalid password.", "error")
                return redirect(url_for("login"))

            # Set Session
            session["username"] = matched["username"]
            session["role"] = matched["role_str"]
            session["eth_address"] = matched["ethAddress"]
            session["email"] = matched["email"]

            flash(f"Welcome back, {matched['username']}! Logged in as {matched['role_str']}.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash(f"No approved user found matching username '{username}' for role '{role}'.", "error")
            return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "").upper()

        if not username or not password or not role:
            flash("Please fill in all required fields.", "error")
            return redirect(url_for("register"))

        try:
            all_parts = bc.get_all_participants()

            # 1. Check if username is already registered (case-insensitive primary key)
            for p in all_parts:
                if p["username"].lower() == username.lower():
                    flash(f"Username '{username}' is already registered on blockchain. Please choose a unique username.", "error")
                    return redirect(url_for("register"))

            # 2. Find an available node eth account
            used_eths = [p["ethAddress"].lower() for p in all_parts]
            available_acc = None
            for acc in bc.w3.eth.accounts:
                if acc.lower() not in used_eths:
                    available_acc = acc
                    break

            if not available_acc:
                # Fallback to cycling node accounts managed by Ganache
                idx = (len(all_parts) + 1) % len(bc.w3.eth.accounts)
                available_acc = bc.w3.eth.accounts[idx]

            tx_hash = bc.register_user_on_chain(username, email, role, available_acc)

            USER_PASSWORDS[username] = werkzeug.security.generate_password_hash(password)

            flash(f"Registration submitted on blockchain! Account PENDING Admin approval.", "info")
            return redirect(url_for("login"))
        except Exception as e:
            flash(f"Registration failed on blockchain: {e}", "error")
            return redirect(url_for("register"))

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        flash("Please log in to access your dashboard.", "warning")
        return redirect(url_for("login"))

    role = session.get("role")
    user_eth = session.get("eth_address")

    if role == "ADMIN":
        participants = bc.get_all_participants()
        system_counts = bc.get_system_counts()
        role_switches = bc.get_all_role_switches()
        return render_template("admin_dashboard.html", participants=participants, system_counts=system_counts, role_switches=role_switches)

    elif role == "SUPPLIER":
        materials = bc.get_supplier_materials(user_eth)
        all_orders = bc.get_all_orders()
        assigned_orders = [o for o in all_orders if o["supplierAddress"].lower() == user_eth.lower()]
        
        # Build Leg 1 map
        leg1_map = {}
        for o in assigned_orders:
            legs = bc.get_order_legs(o["orderId"])
            for l in legs:
                if l["legType_str"] == "LEG1_SUPPLIER_TO_MFG":
                    leg1_map[o["orderId"]] = l

        return render_template("supplier_dashboard.html", materials=materials, assigned_orders=assigned_orders, leg1_map=leg1_map)

    elif role == "MANUFACTURER":
        products = [p for p in bc.get_all_products() if p["manufacturerAddress"].lower() == user_eth.lower()]
        all_orders = bc.get_all_orders()
        mfg_orders = [o for o in all_orders if o["manufacturerAddress"].lower() == user_eth.lower()]
        
        suppliers = [p for p in bc.get_all_participants() if p["role_str"] == "SUPPLIER" and p["status_str"] == "APPROVED"]
        distributors = [p for p in bc.get_all_participants() if p["role_str"] == "DISTRIBUTOR" and p["status_str"] == "APPROVED"]

        leg2_map = {}
        for o in mfg_orders:
            legs = bc.get_order_legs(o["orderId"])
            for l in legs:
                if l["legType_str"] == "LEG2_MFG_TO_DISTRIBUTOR":
                    leg2_map[o["orderId"]] = l

        return render_template("manufacturer_dashboard.html", products=products, orders=mfg_orders, suppliers=suppliers, distributors=distributors, leg2_map=leg2_map)

    elif role == "DISTRIBUTOR":
        all_orders = bc.get_all_orders()
        dist_orders = [o for o in all_orders if o["distributorAddress"].lower() == user_eth.lower()]
        retailers = [p for p in bc.get_all_participants() if p["role_str"] == "RETAILER" and p["status_str"] == "APPROVED"]

        leg3_map = {}
        for o in dist_orders:
            legs = bc.get_order_legs(o["orderId"])
            for l in legs:
                if l["legType_str"] == "LEG3_DISTRIBUTOR_TO_RETAILER":
                    leg3_map[o["orderId"]] = l

        return render_template("distributor_dashboard.html", orders=dist_orders, retailers=retailers, leg3_map=leg3_map)

    elif role == "RETAILER":
        all_orders = bc.get_all_orders()
        ret_orders = [o for o in all_orders if o["retailerAddress"].lower() == user_eth.lower()]

        leg4_map = {}
        for o in ret_orders:
            legs = bc.get_order_legs(o["orderId"])
            for l in legs:
                if l["legType_str"] == "LEG4_RETAILER_TO_CONSUMER":
                    leg4_map[o["orderId"]] = l

        return render_template("retailer_dashboard.html", orders=ret_orders, leg4_map=leg4_map)

    elif role == "CONSUMER":
        products = bc.get_all_products()
        all_orders = bc.get_all_orders()
        my_orders = [o for o in all_orders if user_eth and o["consumerAddress"].lower() == user_eth.lower()]
        if not my_orders:
            my_orders = all_orders
        return render_template("consumer_dashboard.html", products=products, my_orders=my_orders)

    return redirect(url_for("index"))

# --- ADMIN USER APPROVALS ---

@app.route("/admin/approve/<path:user_address>")
def approve_user_route(user_address):
    if session.get("role") != "ADMIN":
        flash("Unauthorized", "error")
        return redirect(url_for("index"))

    try:
        bc.approve_user(user_address, session.get("eth_address"))
        flash(f"Approved user {user_address} on blockchain!", "success")
    except Exception as e:
        flash(f"Approval failed: {e}", "error")

    return redirect(url_for("dashboard"))

@app.route("/admin/reject/<path:user_address>")
def reject_user_route(user_address):
    if session.get("role") != "ADMIN":
        flash("Unauthorized", "error")
        return redirect(url_for("index"))

    try:
        bc.reject_user(user_address, session.get("eth_address"))
        flash(f"Rejected user {user_address} on blockchain.", "info")
    except Exception as e:
        flash(f"Rejection failed: {e}", "error")

    return redirect(url_for("dashboard"))

# --- MATERIAL & PRODUCT REGISTRATION ---

@app.route("/supplier/save_material", methods=["POST"])
def save_material_route():
    current_role = str(session.get("role", "")).upper()
    if not session.get("username") or current_role != "SUPPLIER":
        flash("Unauthorized: Please log in as an approved Supplier account (e.g. ApexMaterials).", "error")
        return redirect(url_for("login"))

    mat_id = request.form.get("id")
    name = request.form.get("name")
    category = request.form.get("category")
    capacity = request.form.get("capacity", 100)
    lead_time_days = request.form.get("lead_time_days", 3)

    # AES encrypt file and pin to IPFS
    file = request.files.get("doc_file")
    ipfs_hash = "QmDefaultMaterialDoc"
    if file and file.filename != "":
        file_bytes = file.read()
        encrypted_payload = encrypt_data(file_bytes, aes_key)
        ipfs_hash, _ = upload_to_ipfs_or_pinata(encrypted_payload, file.filename, PINATA_API_KEY, PINATA_SECRET_KEY)

    try:
        user_eth = session.get("eth_address") or bc.w3.eth.accounts[1]
        tx_hash = bc.save_material(mat_id, name, category, capacity, lead_time_days, ipfs_hash, user_eth)
        flash(f"Material '{name}' saved to blockchain! Tx: {tx_hash[:12]}...", "success")
    except Exception as e:
        err_msg = str(e)
        if "revert" in err_msg.lower() or "only supplier" in err_msg.lower():
            flash(f"Blockchain Revert: Ensure your supplier account has been APPROVED by Admin before registering materials.", "error")
        else:
            flash(f"Failed to save material on chain: {e}", "error")

    return redirect(url_for("dashboard"))

@app.route("/manufacturer/save_product", methods=["POST"])
def save_product_route():
    if session.get("role") != "MANUFACTURER":
        flash("Unauthorized", "error")
        return redirect(url_for("login"))

    prod_id = request.form.get("id")
    name = request.form.get("name")
    category = request.form.get("category")
    price = request.form.get("price", 100)
    req_mats_str = request.form.get("required_materials", "")
    req_mats = [m.strip() for m in req_mats_str.split(",") if m.strip()]

    try:
        tx_hash = bc.save_product(prod_id, name, category, price, req_mats, session.get("eth_address"))
        flash(f"Product '{name}' saved to blockchain! Tx: {tx_hash[:12]}...", "success")
    except Exception as e:
        flash(f"Failed to save product on chain: {e}", "error")

    return redirect(url_for("dashboard"))

# --- ORDERS & ASSIGNMENTS ---

@app.route("/consumer/create_order", methods=["POST"])
def create_order_route():
    current_role = str(session.get("role", "")).upper()
    if not session.get("username") or current_role != "CONSUMER":
        flash("Unauthorized: Please log in as an approved Consumer account (e.g. JohnConsumer).", "error")
        return redirect(url_for("login"))

    product_id = request.form.get("product_id")
    quantity = int(request.form.get("quantity", 1))
    expected_days = int(request.form.get("expected_days", 7))
    expected_delivery_date = int(time.time()) + (expected_days * 86400)

    order_id = f"ORD-{int(time.time())}"
    doc_ipfs_hash = f"QmOrderDoc{order_id}"

    try:
        user_eth = session.get("eth_address")
        tx_hash = bc.create_order(order_id, product_id, quantity, expected_delivery_date, doc_ipfs_hash, user_eth)
        flash(f"Order #{order_id} created on blockchain! Routed to Manufacturer.", "success")

        # Send Email Alert
        send_email_alert(
            to_email=session.get("email"),
            subject=f"Order Placed: #{order_id}",
            body_text=f"Your order #{order_id} for product {product_id} has been submitted on chain.",
            smtp_config=SMTP_CONFIG
        )
    except Exception as e:
        err_msg = str(e)
        if "only consumer" in err_msg.lower() or "revert" in err_msg.lower():
            flash(f"Blockchain Revert: Ensure your consumer account has been APPROVED by Admin before placing orders.", "error")
        else:
            flash(f"Failed to create order on chain: {e}", "error")

    return redirect(url_for("dashboard"))

@app.route("/manufacturer/assign_supplier_distributor", methods=["POST"])
def assign_supplier_distributor_route():
    if session.get("role") != "MANUFACTURER":
        flash("Unauthorized", "error")
        return redirect(url_for("login"))

    order_id = request.form.get("order_id")
    supplier_addr = request.form.get("supplier_addr")
    distributor_addr = request.form.get("distributor_addr")

    try:
        tx_hash = bc.assign_supplier_and_distributor(order_id, supplier_addr, distributor_addr, session.get("eth_address"))
        
        # Save dependency auto record
        dep_id = f"DEP-{order_id}"
        bc.save_dependency(dep_id, order_id, "MAT-101", supplier_addr, session.get("eth_address"), distributor_addr, "0x0000000000000000000000000000000000000000", session.get("eth_address"))

        flash(f"Assigned Supplier & Distributor for Order {order_id} on chain!", "success")
    except Exception as e:
        flash(f"Assignment failed: {e}", "error")

    return redirect(url_for("dashboard"))

@app.route("/distributor/assign_retailer", methods=["POST"])
def assign_retailer_route():
    if session.get("role") != "DISTRIBUTOR":
        flash("Unauthorized", "error")
        return redirect(url_for("login"))

    order_id = request.form.get("order_id")
    retailer_addr = request.form.get("retailer_addr")

    try:
        tx_hash = bc.assign_retailer(order_id, retailer_addr, session.get("eth_address"))
        flash(f"Assigned Retailer for Order {order_id} on chain!", "success")
    except Exception as e:
        flash(f"Retailer assignment failed: {e}", "error")

    return redirect(url_for("dashboard"))

# --- SHIPMENT LEGS ---

@app.route("/leg/create/leg1", methods=["POST"])
def create_leg1_route():
    order_id = request.form.get("order_id")
    to_address = request.form.get("to_address")
    expected_days = int(request.form.get("expected_days", 3))
    expected_date = int(time.time()) + (expected_days * 86400)
    leg_id = f"LEG1-{order_id}"

    try:
        bc.create_shipment_leg(leg_id, order_id, 0, session.get("eth_address"), to_address, expected_date, "QmLeg1Doc", "Supplier dispatch preparing", session.get("eth_address"))
        flash(f"Leg 1 shipment created on chain for Order {order_id}.", "success")
    except Exception as e:
        flash(f"Leg 1 creation failed: {e}", "error")

    return redirect(url_for("dashboard"))

@app.route("/leg/create/leg2", methods=["POST"])
def create_leg2_route():
    order_id = request.form.get("order_id")
    to_address = request.form.get("to_address")
    expected_date = int(time.time()) + (4 * 86400)
    leg_id = f"LEG2-{order_id}"

    try:
        bc.create_shipment_leg(leg_id, order_id, 1, session.get("eth_address"), to_address, expected_date, "QmLeg2Doc", "Manufacturer finished goods dispatch", session.get("eth_address"))
        flash(f"Leg 2 shipment created on chain for Order {order_id}.", "success")
    except Exception as e:
        flash(f"Leg 2 creation failed: {e}", "error")

    return redirect(url_for("dashboard"))

@app.route("/leg/create/leg3", methods=["POST"])
def create_leg3_route():
    order_id = request.form.get("order_id")
    to_address = request.form.get("to_address")
    expected_date = int(time.time()) + (3 * 86400)
    leg_id = f"LEG3-{order_id}"

    try:
        bc.create_shipment_leg(leg_id, order_id, 2, session.get("eth_address"), to_address, expected_date, "QmLeg3Doc", "Distributor regional dispatch", session.get("eth_address"))
        flash(f"Leg 3 shipment created on chain for Order {order_id}.", "success")
    except Exception as e:
        flash(f"Leg 3 creation failed: {e}", "error")

    return redirect(url_for("dashboard"))

@app.route("/leg/create/leg4", methods=["POST"])
def create_leg4_route():
    order_id = request.form.get("order_id")
    to_address = request.form.get("to_address")
    expected_date = int(time.time()) + (2 * 86400)
    leg_id = f"LEG4-{order_id}"

    try:
        bc.create_shipment_leg(leg_id, order_id, 3, session.get("eth_address"), to_address, expected_date, "QmLeg4Doc", "Retailer consumer last-mile delivery", session.get("eth_address"))
        flash(f"Leg 4 shipment created on chain for Order {order_id}.", "success")
    except Exception as e:
        flash(f"Leg 4 creation failed: {e}", "error")

    return redirect(url_for("dashboard"))

@app.route("/leg/update_status", methods=["POST"])
def update_leg_status_route():
    leg_id = request.form.get("leg_id")
    status_int = int(request.form.get("status_int", 1))

    try:
        tx_hash = bc.update_shipment_leg_status(leg_id, status_int, "", "Status updated", session.get("eth_address"))
        leg = bc.get_shipment_leg(leg_id)
        
        # Check rule disruption after status update
        order = bc.get_order(leg["orderId"]) if leg else None
        if leg and order:
            is_disrupted, d_type, d_desc = disruption_engine.check_leg_disruptions(leg, order)
            if is_disrupted:
                d_id = f"DISR-{leg_id}-{int(time.time())}"
                bc.record_disruption(d_id, order["orderId"], leg_id, session.get("eth_address"), d_type, d_desc, session.get("eth_address"))
                
                # SMTP Email Alert
                send_email_alert(
                    to_email="admin@supplychain.eth",
                    subject=f"DISRUPTION ALERT on Order {order['orderId']}",
                    body_text=f"Disruption detected on {leg['legType_str']}. Type: {d_type}. Details: {d_desc}",
                    smtp_config=SMTP_CONFIG
                )
                flash(f"Leg status updated to {leg['status_str']}, but DISRUPTION detected ({d_type})!", "warning")
            else:
                flash(f"Shipment Leg status updated to {leg['status_str']} on blockchain!", "success")
    except Exception as e:
        flash(f"Failed to update leg status: {e}", "error")

    return redirect(url_for("dashboard"))

# --- TRACEABILITY ---

@app.route("/traceability")
def traceability():
    search_id = request.args.get("search_id", "").strip()
    all_orders = bc.get_all_orders()
    target_order = None
    order_legs = []
    legs_by_type = {}

    if search_id:
        target_order = bc.get_order(search_id)
        if not target_order:
            # Check if search_id is a leg ID
            leg = bc.get_shipment_leg(search_id)
            if leg:
                target_order = bc.get_order(leg["orderId"])
    elif all_orders:
        target_order = all_orders[-1]
        search_id = target_order["orderId"]

    if target_order:
        order_legs = bc.get_order_legs(target_order["orderId"])
        for leg in order_legs:
            legs_by_type[leg["legType_str"]] = leg

    return render_template(
        "traceability.html",
        search_id=search_id,
        target_order=target_order,
        order_legs=order_legs,
        legs_by_type=legs_by_type,
        all_orders=all_orders
    )

# --- DISRUPTIONS & RECOVERY ENGINE ---

@app.route("/disruptions")
def disruptions_page():
    disruptions = bc.get_all_disruptions()
    return render_template("disruptions.html", disruptions=disruptions, active_recommendations=None)

@app.route("/disruptions/check", methods=["POST"])
def run_disruption_check_route():
    """Scan all active legs and auto-record rule violations on smart contract."""
    all_legs = bc.get_all_shipment_legs()
    detected_count = 0
    for leg in all_legs:
        order = bc.get_order(leg["orderId"])
        if order:
            is_d, d_type, d_desc = disruption_engine.check_leg_disruptions(leg, order)
            if is_d:
                d_id = f"DISR-{leg['legId']}-{int(time.time())}"
                bc.record_disruption(d_id, order["orderId"], leg["legId"], session.get("eth_address", bc.w3.eth.accounts[0]), d_type, d_desc, session.get("eth_address"))
                detected_count += 1

    if detected_count > 0:
        flash(f"Disruption Engine completed scanner: {detected_count} new disruption(s) detected and recorded on chain!", "warning")
    else:
        flash("Disruption Engine completed scanner: All active shipment legs are operating within normal parameters.", "success")

    return redirect(url_for("disruptions_page"))

@app.route("/disruptions/recommendations/<order_id>/<leg_id>")
def recommendations_route(order_id, leg_id):
    order = bc.get_order(order_id)
    disruptions = bc.get_all_disruptions()
    
    target_role = "SUPPLIER"
    current_part = order.get("supplierAddress", "")
    if "LEG2" in leg_id:
        target_role = "DISTRIBUTOR"
        current_part = order.get("distributorAddress", "")
    elif "LEG3" in leg_id:
        target_role = "RETAILER"
        current_part = order.get("retailerAddress", "")

    recommendations = disruption_engine.recommend_alternate_participants(target_role, order_id, current_part)
    impact_analysis = disruption_engine.calculate_downstream_impact(order_id, delay_days=4)

    return render_template(
        "disruptions.html",
        disruptions=disruptions,
        active_recommendations=recommendations,
        target_order_id=order_id,
        target_role=target_role,
        impact_analysis=impact_analysis
    )

@app.route("/disruptions/confirm_replacement", methods=["POST"])
def confirm_replacement_route():
    order_id = request.form.get("order_id")
    role = request.form.get("role", "").upper()
    new_participant_addr = request.form.get("new_participant_addr")
    reason = request.form.get("reason", "Disruption replacement")

    try:
        sender_eth = session.get("eth_address")
        if role == "SUPPLIER":
            bc.update_order_supplier(order_id, new_participant_addr, reason, sender_eth)
        elif role == "DISTRIBUTOR":
            bc.update_order_distributor(order_id, new_participant_addr, reason, sender_eth)
        elif role == "RETAILER":
            bc.update_order_retailer(order_id, new_retailer_addr=new_participant_addr, reason=reason, sender_eth=sender_eth)

        # SMTP Notification to affected parties
        new_user = bc.get_participant(new_participant_addr)
        if new_user:
            send_email_alert(
                to_email=new_user["email"],
                subject=f"Order Role Reassignment: #{order_id}",
                body_text=f"You have been assigned as the replacement {role} for Order #{order_id} on the blockchain.",
                smtp_config=SMTP_CONFIG
            )

        flash(f"Successfully confirmed replacement {role} ({new_participant_addr[:8]}...) for Order #{order_id} on Blockchain!", "success")
    except Exception as e:
        flash(f"Failed to record role switch on chain: {e}", "error")

    return redirect(url_for("disruptions_page"))

# ==========================================
# MAIN EXECUTION ENTRYPOINT
# ==========================================
if __name__ == "__main__":
    print("====================================================")
    print(" Decentralized Supply Chain Management System Ready")
    print(f" Web3 Node: {GANACHE_URL}")
    print(f" Deployed Contract Address: {bc.contract_address}")
    print("====================================================")
    app.run(host="127.0.0.1", port=5000, debug=True)
