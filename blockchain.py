import json
import os
import time
from web3 import Web3
from eth_tester import EthereumTester
from web3.providers.eth_tester import EthereumTesterProvider

class BlockchainInterface:
    def __init__(self, rpc_url="http://127.0.0.1:8545", contract_address=None):
        self.rpc_url = rpc_url
        self.w3 = None
        self.contract = None
        self.contract_address = contract_address
        self.abi = None
        self.bytecode = None
        self.is_tester = False

        self._connect_web3()
        self._load_or_compile_contract()

    def _connect_web3(self):
        """Connect to Ganache RPC or fall back to EthereumTester."""
        try:
            w3_temp = Web3(Web3.HTTPProvider(self.rpc_url))
            if w3_temp.is_connected():
                self.w3 = w3_temp
                self.is_tester = False
                print(f"[Web3] Successfully connected to Ganache node at {self.rpc_url}")
                return
        except Exception as e:
            print(f"[Web3 Warning] Could not connect to Ganache RPC ({e}).")

        # Fallback to EthereumTester in-memory blockchain
        print("[Web3] Falling back to EthereumTester in-memory blockchain engine.")
        tester = EthereumTester()
        self.w3 = Web3(EthereumTesterProvider(tester))
        self.is_tester = True

    def _load_or_compile_contract(self):
        """Load compiled Truffle artifact or compile SupplyChain.sol using py-solc-x."""
        truffle_artifact_path = os.path.join("build", "contracts", "SupplyChain.json")
        
        if os.path.exists(truffle_artifact_path):
            with open(truffle_artifact_path, "r") as f:
                artifact = json.load(f)
                self.abi = artifact.get("abi")
                self.bytecode = artifact.get("bytecode")
                # Get deployed address if available
                networks = artifact.get("networks", {})
                if networks and not self.contract_address:
                    last_net = list(networks.values())[-1]
                    self.contract_address = last_net.get("address")
            print("[Blockchain] Loaded Truffle compiled contract ABI and Bytecode.")
        else:
            # Dynamically compile using py-solc-x or use pre-compiled ABI
            self._compile_with_solcx()

        # Deploy if no address set or code at address is empty (e.g. fresh in-memory test node)
        code_at_addr = b''
        if self.contract_address:
            try:
                code_at_addr = self.w3.eth.get_code(self.contract_address)
            except Exception:
                code_at_addr = b''

        if not self.contract_address or code_at_addr == b'' or code_at_addr == b'0x':
            print("[Blockchain] No active contract code found at stored address. Deploying fresh contract...")
            self.deploy_contract()
        elif self.contract_address and self.abi:
            self.contract = self.w3.eth.contract(address=self.contract_address, abi=self.abi)
            print(f"[Blockchain] Attached to existing contract at: {self.contract_address}")

    def _compile_with_solcx(self):
        """Compile contracts/SupplyChain.sol via py-solc-x."""
        try:
            solcx_dir = os.path.abspath(os.path.join("keys", "solcx_bin"))
            os.makedirs(solcx_dir, exist_ok=True)
            os.environ["SOLCX_BINARY_PATH"] = solcx_dir

            from solcx import compile_standard, install_solc
            try:
                install_solc("0.8.20")
            except Exception:
                pass

            sol_path = os.path.join("contracts", "SupplyChain.sol")
            with open(sol_path, "r", encoding="utf-8") as f:
                source_code = f.read()

            compiled_sol = compile_standard({
                "language": "Solidity",
                "sources": {"SupplyChain.sol": {"content": source_code}},
                "settings": {
                    "evmVersion": "london",
                    "optimizer": {
                        "enabled": True,
                        "runs": 200
                    },
                    "outputSelection": {
                        "*": {"*": ["abi", "metadata", "evm.bytecode", "evm.bytecode.sourceMap"]}
                    }
                }
            }, solc_version="0.8.20")

            self.abi = compiled_sol["contracts"]["SupplyChain.sol"]["SupplyChain"]["abi"]
            self.bytecode = compiled_sol["contracts"]["SupplyChain.sol"]["SupplyChain"]["evm"]["bytecode"]["object"]
            print("[Blockchain] Successfully compiled SupplyChain.sol with py-solc-x.")
        except Exception as e:
            print(f"[Blockchain Error] Solcx compilation failed ({e}). Using minimal ABI fallback.")
            self._use_fallback_abi()

    def _use_fallback_abi(self):
        """Fallback ABI if compilation tools aren't present."""
        # We save built ABI to build/contracts/SupplyChain.json for future runs
        os.makedirs(os.path.join("build", "contracts"), exist_ok=True)

    def deploy_contract(self, deployer_account=None):
        """Deploy SupplyChain contract to the connected network."""
        if not self.abi or not self.bytecode:
            raise Exception("ABI or Bytecode missing for deployment")

        accounts = self.w3.eth.accounts
        deployer = deployer_account or accounts[0]

        SupplyChainContract = self.w3.eth.contract(abi=self.abi, bytecode=self.bytecode)
        tx_hash = SupplyChainContract.constructor().transact({'from': deployer, 'gas': 6000000})
        tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        self.contract_address = tx_receipt.contractAddress
        self.contract = self.w3.eth.contract(address=self.contract_address, abi=self.abi)
        print(f"[Blockchain] Deployed SupplyChain contract to address: {self.contract_address}")
        
        # Save artifact for persistence
        artifact = {"abi": self.abi, "bytecode": self.bytecode, "networks": {"5777": {"address": self.contract_address}}}
        os.makedirs(os.path.join("build", "contracts"), exist_ok=True)
        with open(os.path.join("build", "contracts", "SupplyChain.json"), "w") as f:
            json.dump(artifact, f, indent=2)

        return self.contract_address

    def get_account_for_user(self, eth_address=None, required_role=None):
        accounts = self.w3.eth.accounts
        if eth_address and eth_address in accounts:
            if required_role:
                p = self.get_participant(eth_address)
                if p and p.get("role_str") == required_role and p.get("status_str") == "APPROVED":
                    return eth_address
            else:
                return eth_address

        if required_role:
            for acc in accounts:
                p = self.get_participant(acc)
                if p and p.get("role_str") == required_role and p.get("status_str") == "APPROVED":
                    return acc

        if eth_address and eth_address in accounts:
            return eth_address

        return accounts[0]

    # --- CONTRACT CALL WRAPPERS ---

    def register_user_on_chain(self, username, email, role_str, eth_address=None, private_key=None):
        account = eth_address or self.w3.eth.accounts[0]
        role_map = {
            "ADMIN": 1, "SUPPLIER": 2, "MANUFACTURER": 3,
            "DISTRIBUTOR": 4, "RETAILER": 5, "CONSUMER": 6
        }
        role_num = role_map.get(role_str.upper(), 6)

        tx_func_name = {
            1: "saveAdmin",
            2: "saveSupplier",
            3: "saveManufacturer",
            4: "saveDistributor",
            5: "saveRetailer",
            6: "saveConsumer"
        }[role_num]

        tx_func = getattr(self.contract.functions, tx_func_name)
        if private_key:
            tx_dict = {
                'from': account,
                'nonce': self.w3.eth.get_transaction_count(account),
                'gas': 500000,
                'gasPrice': self.w3.eth.gas_price
            }
            try:
                tx_dict['chainId'] = self.w3.eth.chain_id
            except Exception:
                pass

            tx = tx_func(username, email).build_transaction(tx_dict)
            signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=private_key)
            raw_tx_bytes = getattr(signed_tx, 'raw_transaction', getattr(signed_tx, 'rawTransaction', None))
            tx_hash = self.w3.eth.send_raw_transaction(raw_tx_bytes)
        else:
            tx_hash = tx_func(username, email).transact({'from': account})

        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx_hash.hex()

    def approve_user(self, user_eth_address, admin_eth_address=None):
        admin = self.get_account_for_user(admin_eth_address, required_role="ADMIN")
        tx_hash = self.contract.functions.approveUser(user_eth_address).transact({'from': admin})
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx_hash.hex()

    def reject_user(self, user_eth_address, admin_eth_address=None):
        admin = self.get_account_for_user(admin_eth_address, required_role="ADMIN")
        tx_hash = self.contract.functions.rejectUser(user_eth_address).transact({'from': admin})
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx_hash.hex()

    def save_material(self, mat_id, name, category, capacity, lead_time_days, doc_ipfs_hash, supplier_eth):
        account = self.get_account_for_user(supplier_eth, required_role="SUPPLIER")
        tx_hash = self.contract.functions.saveMaterial(
            mat_id, name, category, int(capacity), int(lead_time_days), doc_ipfs_hash
        ).transact({'from': account})
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx_hash.hex()

    def save_product(self, prod_id, name, category, price, required_mat_ids, mfg_eth):
        account = self.get_account_for_user(mfg_eth, required_role="MANUFACTURER")
        tx_hash = self.contract.functions.saveProduct(
            prod_id, name, category, int(price), required_mat_ids
        ).transact({'from': account})
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx_hash.hex()

    def create_order(self, order_id, product_id, quantity, expected_delivery_date, doc_ipfs_hash, consumer_eth):
        account = self.get_account_for_user(consumer_eth, required_role="CONSUMER")
        tx_hash = self.contract.functions.createOrder(
            order_id, product_id, int(quantity), int(expected_delivery_date), doc_ipfs_hash
        ).transact({'from': account})
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx_hash.hex()

    def assign_supplier_and_distributor(self, order_id, supplier_addr, distributor_addr, mfg_eth):
        account = self.get_account_for_user(mfg_eth, required_role="MANUFACTURER")
        tx_hash = self.contract.functions.assignSupplierAndDistributor(
            order_id, supplier_addr, distributor_addr
        ).transact({'from': account})
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx_hash.hex()

    def assign_retailer(self, order_id, retailer_addr, dist_eth):
        account = self.get_account_for_user(dist_eth, required_role="DISTRIBUTOR")
        tx_hash = self.contract.functions.assignRetailer(
            order_id, retailer_addr
        ).transact({'from': account})
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx_hash.hex()

    def save_dependency(self, dep_id, order_id, mat_id, sup_addr, mfg_addr, dist_addr, ret_addr, sender_eth):
        account = self.get_account_for_user(sender_eth)
        tx_hash = self.contract.functions.saveDependency(
            dep_id, order_id, mat_id, sup_addr, mfg_addr, dist_addr, ret_addr
        ).transact({'from': account})
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx_hash.hex()

    def create_shipment_leg(self, leg_id, order_id, leg_type_int, from_addr, to_addr, expected_date, doc_hash, notes, sender_eth):
        account = self.get_account_for_user(sender_eth)
        tx_hash = self.contract.functions.createShipmentLeg(
            leg_id, order_id, leg_type_int, from_addr, to_addr, int(expected_date), doc_hash, notes
        ).transact({'from': account})
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx_hash.hex()

    def update_shipment_leg_status(self, leg_id, status_int, doc_hash, notes, sender_eth):
        account = self.get_account_for_user(sender_eth)
        tx_hash = self.contract.functions.updateShipmentLegStatus(
            leg_id, status_int, doc_hash, notes
        ).transact({'from': account})
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx_hash.hex()

    def record_disruption(self, disruption_id, order_id, leg_id, participant_addr, disruption_type, description, reporter_eth):
        account = self.get_account_for_user(reporter_eth)
        tx_hash = self.contract.functions.recordDisruption(
            disruption_id, order_id, leg_id, participant_addr, disruption_type, description
        ).transact({'from': account})
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx_hash.hex()

    def update_order_supplier(self, order_id, new_supplier_addr, reason, sender_eth):
        account = self.get_account_for_user(sender_eth)
        tx_hash = self.contract.functions.updateOrderSupplier(
            order_id, new_supplier_addr, reason
        ).transact({'from': account})
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx_hash.hex()

    def update_order_distributor(self, order_id, new_distributor_addr, reason, sender_eth):
        account = sender_eth or self.w3.eth.accounts[0]
        tx_hash = self.contract.functions.updateOrderDistributor(
            order_id, new_distributor_addr, reason
        ).transact({'from': account})
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx_hash.hex()

    def update_order_retailer(self, order_id, new_retailer_addr, reason, sender_eth):
        account = sender_eth or self.w3.eth.accounts[0]
        tx_hash = self.contract.functions.updateOrderRetailer(
            order_id, new_retailer_addr, reason
        ).transact({'from': account})
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx_hash.hex()

    # --- QUERY GETTERS ---

    def get_participant(self, eth_address):
        try:
            p = self.contract.functions.participants(eth_address).call()
            role_names = ["NONE", "ADMIN", "SUPPLIER", "MANUFACTURER", "DISTRIBUTOR", "RETAILER", "CONSUMER"]
            status_names = ["PENDING", "APPROVED", "REJECTED"]
            if p[3] != "0x0000000000000000000000000000000000000000":
                return {
                    "username": p[0],
                    "role_int": p[1],
                    "role_str": role_names[p[1]],
                    "email": p[2],
                    "ethAddress": p[3],
                    "status_int": p[4],
                    "status_str": status_names[p[4]],
                    "registrationTime": p[5]
                }
        except Exception as e:
            print(f"[Query Error] get_participant: {e}")
        return None

    def get_all_participants(self):
        participants = []
        try:
            count = self.contract.functions.getParticipantCount().call()
            for i in range(count):
                addr = self.contract.functions.participantAddresses(i).call()
                p = self.get_participant(addr)
                if p:
                    participants.append(p)
        except Exception as e:
            print(f"[Query Error] get_all_participants: {e}")
        return participants

    def get_material(self, mat_id):
        try:
            m = self.contract.functions.materials(mat_id).call()
            if m[0]:
                return {
                    "id": m[0],
                    "name": m[1],
                    "category": m[2],
                    "capacity": m[3],
                    "leadTimeDays": m[4],
                    "supplierAddress": m[5],
                    "status": m[6],
                    "documentIpfsHash": m[7],
                    "createdAt": m[8]
                }
        except Exception as e:
            print(f"[Query Error] get_material: {e}")
        return None

    def get_all_materials(self):
        materials = []
        idx = 0
        while True:
            try:
                m_id = self.contract.functions.materialIds(idx).call()
                m = self.get_material(m_id)
                if m:
                    materials.append(m)
                idx += 1
            except Exception:
                break
        return materials

    def get_supplier_materials(self, supplier_addr):
        all_mats = self.get_all_materials()
        return [m for m in all_mats if m["supplierAddress"].lower() == supplier_addr.lower()]

    def get_product(self, prod_id):
        try:
            p = self.contract.functions.products(prod_id).call()
            req_mats = self.contract.functions.getProductRequiredMaterials(prod_id).call()
            if p[0]:
                return {
                    "id": p[0],
                    "name": p[1],
                    "category": p[2],
                    "price": p[3],
                    "manufacturerAddress": p[4],
                    "requiredMaterialIds": req_mats,
                    "createdAt": p[5]
                }
        except Exception as e:
            print(f"[Query Error] get_product: {e}")
        return None

    def get_all_products(self):
        products = []
        idx = 0
        while True:
            try:
                p_id = self.contract.functions.productIds(idx).call()
                p = self.get_product(p_id)
                if p:
                    products.append(p)
                idx += 1
            except Exception:
                break
        return products

    def get_order(self, order_id):
        try:
            o = self.contract.functions.orders(order_id).call()
            order_statuses = ["CREATED", "WITH_MANUFACTURER", "SUPPLIER_ASSIGNED", "IN_PRODUCTION", "DISTRIBUTOR_ASSIGNED", "RETAILER_ASSIGNED", "SHIPPED", "DELIVERED", "DISRUPTED"]
            if o[0]:
                return {
                    "orderId": o[0],
                    "consumerAddress": o[1],
                    "productId": o[2],
                    "quantity": o[3],
                    "expectedDeliveryDate": o[4],
                    "manufacturerAddress": o[5],
                    "supplierAddress": o[6],
                    "distributorAddress": o[7],
                    "retailerAddress": o[8],
                    "status_int": o[9],
                    "status_str": order_statuses[o[9]],
                    "createdAt": o[10],
                    "documentIpfsHash": o[11]
                }
        except Exception as e:
            print(f"[Query Error] get_order: {e}")
        return None

    def get_all_orders(self):
        orders = []
        idx = 0
        while True:
            try:
                o_id = self.contract.functions.orderIds(idx).call()
                o = self.get_order(o_id)
                if o:
                    orders.append(o)
                idx += 1
            except Exception:
                break
        return orders

    def get_shipment_leg(self, leg_id):
        try:
            l = self.contract.functions.shipmentLegs(leg_id).call()
            leg_statuses = ["NOT_STARTED", "PREPARING", "SHIPPED", "IN_TRANSIT", "DELAYED", "DELIVERED", "DISRUPTED"]
            leg_types = ["LEG1_SUPPLIER_TO_MFG", "LEG2_MFG_TO_DISTRIBUTOR", "LEG3_DISTRIBUTOR_TO_RETAILER", "LEG4_RETAILER_TO_CONSUMER"]
            if l[0]:
                return {
                    "legId": l[0],
                    "orderId": l[1],
                    "legType_int": l[2],
                    "legType_str": leg_types[l[2]],
                    "fromAddress": l[3],
                    "toAddress": l[4],
                    "status_int": l[5],
                    "status_str": leg_statuses[l[5]],
                    "expectedDate": l[6],
                    "actualDate": l[7],
                    "lastUpdated": l[8],
                    "documentHash": l[9],
                    "notes": l[10]
                }
        except Exception as e:
            print(f"[Query Error] get_shipment_leg: {e}")
        return None

    def get_all_shipment_legs(self):
        legs = []
        idx = 0
        while True:
            try:
                l_id = self.contract.functions.shipmentLegIds(idx).call()
                leg = self.get_shipment_leg(l_id)
                if leg:
                    legs.append(leg)
                idx += 1
            except Exception:
                break
        return legs

    def get_order_legs(self, order_id):
        legs = []
        try:
            leg_ids = self.contract.functions.getOrderLegIds(order_id).call()
            for l_id in leg_ids:
                leg = self.get_shipment_leg(l_id)
                if leg:
                    legs.append(leg)
        except Exception as e:
            print(f"[Query Error] get_order_legs: {e}")
        return legs

    def get_disruption(self, disruption_id):
        try:
            d = self.contract.functions.disruptions(disruption_id).call()
            if d[0]:
                return {
                    "disruptionId": d[0],
                    "orderId": d[1],
                    "legId": d[2],
                    "reportedBy": d[3],
                    "participantAddress": d[4],
                    "disruptionType": d[5],
                    "description": d[6],
                    "timestamp": d[7],
                    "resolved": d[8]
                }
        except Exception as e:
            print(f"[Query Error] get_disruption: {e}")
        return None

    def get_all_disruptions(self):
        disruptions = []
        idx = 0
        while True:
            try:
                d_id = self.contract.functions.disruptionIds(idx).call()
                d = self.get_disruption(d_id)
                if d:
                    disruptions.append(d)
                idx += 1
            except Exception:
                break
        return disruptions

    def get_participant_disruptions_count(self, participant_addr):
        all_d = self.get_all_disruptions()
        return sum(1 for d in all_d if d.get("participantAddress", "").lower() == participant_addr.lower())

    def get_role_switch(self, switch_id):
        try:
            s = self.contract.functions.roleSwitches(switch_id).call()
            role_names = ["NONE", "ADMIN", "SUPPLIER", "MANUFACTURER", "DISTRIBUTOR", "RETAILER", "CONSUMER"]
            if s[0]:
                return {
                    "switchId": s[0],
                    "orderId": s[1],
                    "legId": s[2],
                    "oldParticipant": s[3],
                    "newParticipant": s[4],
                    "role_int": s[5],
                    "role_str": role_names[s[5]],
                    "reason": s[6],
                    "timestamp": s[7]
                }
        except Exception as e:
            print(f"[Query Error] get_role_switch: {e}")
        return None

    def get_all_role_switches(self):
        switches = []
        idx = 0
        while True:
            try:
                s_id = self.contract.functions.roleSwitchIds(idx).call()
                sw = self.get_role_switch(s_id)
                if sw:
                    switches.append(sw)
                idx += 1
            except Exception:
                break
        return switches

    def get_order_dependencies(self, order_id):
        deps = []
        idx = 0
        while True:
            try:
                dep_id = self.contract.functions.dependencyIds(idx).call()
                d = self.contract.functions.dependencies(dep_id).call()
                if d[1] == order_id:
                    deps.append({
                        "id": d[0],
                        "orderId": d[1],
                        "materialId": d[2],
                        "supplierAddress": d[3],
                        "manufacturerAddress": d[4],
                        "distributorAddress": d[5],
                        "retailerAddress": d[6],
                        "timestamp": d[7]
                    })
                idx += 1
            except Exception:
                break
        return deps

    def get_system_counts(self):
        """Analytics counters for Admin dashboard."""
        return {
            "participants": len(self.get_all_participants()),
            "orders": len(self.get_all_orders()),
            "legs": len(self.get_all_shipment_legs()),
            "disruptions": len(self.get_all_disruptions()),
            "switches": len(self.get_all_role_switches())
        }
