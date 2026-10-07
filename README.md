# Blockchain-Based Supply Chain Management System

A decentralized, end-to-end supply chain tracking and disruption recovery system powered by **Solidity**, **Ethereum / Ganache**, **Web3.py**, **Flask**, **AES GCM Encryption**, **IPFS / Pinata**, and **SMTP Email Alerts**.

---

## 🌟 Key Features

1. **Decentralized Business Logic on Smart Contracts**:
   - Written in Solidity (`contracts/SupplyChain.sol`) with multi-role state machine governance.
   - Immutable records for user approvals, raw material specs, finished products, consumer orders, shipment legs, disruptions, and role switches.

2. **End-to-End 4-Leg Product Path Tracking**:
   - `Consumer Order` &rarr; `Leg 1 (Supplier -> Mfg)` &rarr; `Leg 2 (Mfg -> Dist)` &rarr; `Leg 3 (Dist -> Retailer)` &rarr; `Leg 4 (Retailer -> Consumer)`.

3. **Rule-Based Disruption Detection & Recovery Engine**:
   - Automatic scanner evaluating expected delivery dates, delayed leg flags, and supplier material capacity breaches.
   - Downstream impact analysis recalculating projected consumer delivery dates.
   - Candidate ranking algorithm evaluating supplier/distributor/retailer candidates by capacity, lead time, availability, and historical disruption score.

4. **Cryptographic Security & File Storage**:
   - Sensitive document uploads (e.g. quality certs, invoices) are encrypted client/server side with 256-bit AES GCM (`keys/aes_key.bin`).
   - Pinning encrypted payloads to IPFS / Pinata with cryptographic SHA-256 state hashes stored on-chain.

5. **Multi-Role Dashboards & Sleek Glassmorphism UI**:
   - **Admin**: Approve/reject user registrations, inspect system audit logs, and visualize analytics charts (Chart.js).
   - **Supplier**: Register raw materials, process Leg 1 shipments.
   - **Manufacturer**: Register products, assign suppliers and distributors, process Leg 2 shipments, confirm disruption role switches.
   - **Distributor**: Assign regional retailers, process Leg 3 shipments, confirm retailer role switches.
   - **Retailer**: Process Leg 4 last-mile consumer delivery updates.
   - **Consumer**: Browse finished product catalog, submit orders, and track order path timeline.

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10+
- Ganache (Optional: runs on `http://127.0.0.1:8545`; falls back automatically to EthTester if Ganache is offline).

### 2. Installation
```bash
# Clone or navigate to the repository folder
cd c:\Users\TruProjects\Desktop\BC

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Deploy Smart Contract (Optional Truffle Step)
```bash
truffle migrate --reset
```
*Note: If Truffle is not installed, `app.py` automatically compiles `SupplyChain.sol` and deploys it to the node on startup!*

### 4. Launch Application
```bash
python app.py
```
Open your browser and navigate to: **`http://127.0.0.1:5000`**

---

## 🔐 Default Demo Accounts (Pre-Seeded)

| Role | Username | Password |
|---|---|---|
| **Admin** | `admin` | `admin` |
| **Supplier** | `ApexMaterials` | `supplier123` |
| **Manufacturer** | `OmniMfgCorp` | `mfg123` |
| **Distributor** | `ExpressDistributors` | `dist123` |
| **Retailer** | `MetroRetailStore` | `retailer123` |
| **Consumer** | `JohnConsumer` | `consumer123` |

---

## 📊 Disruption Recovery Workflow

1. A shipment leg is marked as **DELAYED** or exceeds its expected delivery timestamp.
2. The **Disruption Engine** flags the leg and calls `recordDisruption()` on `SupplyChain.sol`.
3. Downstream impact analysis recalculates the consumer delivery date.
4. The system calculates rank scores for all alternate approved participants.
5. The Manufacturer or Distributor confirms the replacement candidate, executing `updateOrderSupplier()`, `updateOrderDistributor()`, or `updateOrderRetailer()` on-chain.
