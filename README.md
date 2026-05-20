##---

# 🧬 Pharmadex

![Django](https://img.shields.io/badge/Django-5.x-green)
![Python](https://img.shields.io/badge/Python-3.11+-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-DB-blue)
![License](https://img.shields.io/badge/License-Proprietary-black)
![Status](https://img.shields.io/badge/Status-Active%20Development-orange)

> **Pharmadex** is a multi-tenant, multi-store (pharmacy) ERP & CRM system designed to streamline operations, reduce errors, and improve decision-making across pharmacy networks.

---

## 🚀 Overview

Pharmadex is built as a **full operating system for pharmacies**—not just a tool.

It centralizes:

* Inventory & stock control
* Sales & POS
* Suppliers & procurement
* Patient & prescription data
* Business intelligence & insights

With a strong focus on:

> **Accuracy · Speed · Traceability · Intelligence**

---

## 🧩 Core Modules

### 🏢 Multi-Tenant & Multi-Pharmacy

* Multiple pharmacy organizations (tenants)
* Multi-branch support with scoped data
* Role-based access control:

  * Admin
  * Pharmacist
  * Cashier
  * Manager
* Secure tenant isolation
* Pharmacy context switching

---

### 📦 Inventory Management

* Real-time stock per pharmacy
* Batch tracking (lot number, expiry date)
* Expiry monitoring & alerts
* Low-stock thresholds
* Stock adjustments (with audit logs)
* Inter-pharmacy transfers

---

### 🧾 Point of Sale (POS)

* Fast product search (name, barcode)
* Barcode scanning
* Multi-payment support
* Receipt generation
* Optimized for high-speed environments
* Offline-first capability (resilient to poor connectivity)

---

### 🚚 Procurement & Suppliers

* Supplier management
* Purchase order workflows
* Goods receiving (batch-aware)
* Invoice & cost tracking

---

### 👤 Patient & CRM

* Patient profiles
* Prescription history
* Purchase history
* Notes (allergies, chronic conditions, flags)

---

### 💊 Prescription Management

* Prescription recording
* Dispensing logs
* Validation workflows
* Traceable medication history

---

### 📊 Reporting (Baseline)

* Daily / monthly sales reports
* Inventory reports
* Profit tracking
* Transaction analytics

---

## 🧠 Advanced Features (Roadmap)

### ⚠️ Decision Support (AI-Assisted)

* Drug interaction detection
* Contraindication alerts
* Duplicate therapy warnings
* Safer alternative suggestions

> ⚠️ Designed to assist pharmacists—not replace clinical judgment.

---

### 📈 Smart Inventory

* Demand forecasting per pharmacy
* Auto-restock suggestions
* Dead stock detection
* Expiry risk prediction

---

### 📊 Business Intelligence

* Top-selling drugs
* Revenue trends
* Pharmacy comparisons
* Margin analysis

---

### 🔁 CRM Enhancements

* Refill reminders
* Chronic patient tracking
* Behavioral insights

---

### 🔗 Ecosystem Integrations (Future)

* E-prescriptions
* Hospital/clinic systems
* Insurance processing

---

## 🧠 Pharmacy Ops (Why This Matters)

Pharmacies  are not typical retail systems.

They require:

* **Zero tolerance for errors** (patient safety)
* **Expiry-aware inventory**
* **Fast workflows under pressure**
* **Drug substitution flexibility**
* **Tight margin optimization**

Pharmadex is designed to:

> reduce cognitive load, enforce safe workflows, and prevent costly mistakes.

---

## 🛠 Tech Stack

| Layer        | Technology                          |
| ------------ | ----------------------------------- |
| Backend      | Python, Django                      |
| Frontend     | Django Templates, HTMX, TailwindCSS |
| Database     | PostgreSQL                          |
| UI           | FontAwesome                         |
| Architecture | Multi-tenant + pharmacy scoping        |

---

## 🧱 Architecture Notes

* Tenant-aware data isolation
* Pharmacy-level query scoping
* Custom middleware for active context
* Audit-first design (critical for compliance)
* Extensible module structure (ERP-style)

---

## 📂 Project Structure (Example)

```
pharmadex/
│
├── core/              # shared logic, base models
├── tenants/           # tenant + pharmacy management
├── inventory/         # stock, batches, expiry
├── sales/             # POS, transactions
├── suppliers/         # procurement workflows
├── patients/          # CRM layer
├── prescriptions/     # medical records
├── analytics/         # reports & BI
└── ai/                # decision support (future)
```

---

## ⚙️ Setup (Dev)

```bash
git clone https://github.com/your-org/pharmadex.git
cd pharmadex

python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate

pip install -r requirements.txt

python manage.py migrate
python manage.py runserver
```

---

## 🎯 Vision

> **Pharmadex aims to become the operating system for modern pharmacies.**

A platform that doesn’t just manage data—but actively:

* reduces losses
* prevents errors
* improves decisions
* and scales with pharmacy networks

---

## 🤝 Contributing

Currently private / controlled development.
If you’re collaborating internally, follow:

* consistent app/module boundaries
* tenant-safe queries
* audit logging on all critical actions

---

## 📜 License

Proprietary — All rights reserved.

