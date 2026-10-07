import time
import datetime

class DisruptionEngine:
    def __init__(self, blockchain_interface):
        self.bc = blockchain_interface

    def check_leg_disruptions(self, leg_data: dict, order_data: dict) -> tuple:
        """
        Evaluate rule-based disruption conditions on a leg:
        1. Past expected date & not DELIVERED.
        2. Explicit status DELAYED or DISRUPTED.
        3. Material capacity insufficiency (Leg 1).
        Returns (is_disrupted, disruption_type, description).
        """
        now = int(time.time())
        status = leg_data.get("status_str", leg_data.get("status", ""))
        leg_type = leg_data.get("legType_str", leg_data.get("legType", ""))
        expected_date = int(leg_data.get("expectedDate", 0))

        # Rule 1: Delay past expected date
        if status not in ["DELIVERED"] and expected_date > 0 and now > expected_date:
            days_overdue = (now - expected_date) // 86400
            return True, "EXPIRED_SCHEDULE", f"Leg shipment is overdue by {days_overdue} day(s) past expected date."

        # Rule 2: Explicit DELAYED status
        if status in ["DELAYED", "DISRUPTED"]:
            return True, "TRANSPORT_DELAY", "Carrier or participant flagged shipment as delayed/disrupted."

        # Rule 3: Leg 1 Material Capacity Issue
        if leg_type == "LEG1_SUPPLIER_TO_MFG":
            mat_id = leg_data.get("materialId")
            if mat_id:
                mat = self.bc.get_material(mat_id)
                quantity = int(order_data.get("quantity", 1))
                if mat and int(mat.get("capacity", 0)) < quantity:
                    return True, "MATERIAL_CAPACITY_BREACH", f"Supplier capacity ({mat.get('capacity')}) is lower than required order quantity ({quantity})."

        return False, "", ""

    def calculate_downstream_impact(self, order_id: str, delay_days: int = 3) -> dict:
        """
        Impact analysis: trace downstream dependencies and calculate estimated impact on final consumer delivery date.
        """
        order = self.bc.get_order(order_id)
        current_expected = int(order.get("expectedDeliveryDate", 0))
        new_expected = current_expected + (delay_days * 86400) if current_expected > 0 else int(time.time()) + (delay_days * 86400)

        dependencies = self.bc.get_order_dependencies(order_id)

        return {
            "order_id": order_id,
            "delay_days": delay_days,
            "original_delivery_date": datetime.datetime.fromtimestamp(current_expected).strftime("%Y-%m-%d") if current_expected > 0 else "N/A",
            "projected_delivery_date": datetime.datetime.fromtimestamp(new_expected).strftime("%Y-%m-%d"),
            "affected_dependencies_count": len(dependencies),
            "consumer_address": order.get("consumerAddress", ""),
            "manufacturer_address": order.get("manufacturerAddress", "")
        }

    def recommend_alternate_participants(self, role: str, order_id: str, current_participant_addr: str) -> list:
        """
        Generate ranked recommendations for alternate participants of a given role.
        Ranking Criteria:
        - Must be APPROVED user.
        - Higher capacity / efficiency score.
        - Shorter lead time.
        - Lower historical disruption count.
        """
        all_participants = self.bc.get_all_participants()
        target_role_str = role.upper()

        candidates = []
        for p in all_participants:
            # Check role match and exclude current participant & unapproved users
            p_role = str(p.get("role_str", "")).upper()
            if p_role == target_role_str and p.get("ethAddress").lower() != current_participant_addr.lower() and p.get("status_str") == "APPROVED":
                candidates.append(p)

        scored_candidates = []
        for c in candidates:
            c_addr = c.get("ethAddress")
            
            # Fetch past disruption score for this participant
            past_disruptions = self.bc.get_participant_disruptions_count(c_addr)
            
            # Metrics calculation
            base_score = 100
            disruption_penalty = past_disruptions * 15
            
            # Supplier capacity / lead time boost if supplier
            capacity = 100
            lead_time = 3
            if target_role_str == "SUPPLIER":
                mats = self.bc.get_supplier_materials(c_addr)
                if mats:
                    capacity = max([int(m.get("capacity", 50)) for m in mats])
                    lead_time = min([int(m.get("leadTimeDays", 3)) for m in mats])

            score = base_score + (capacity * 0.2) - (lead_time * 5) - disruption_penalty
            
            scored_candidates.append({
                "username": c.get("username"),
                "ethAddress": c_addr,
                "email": c.get("email"),
                "role": target_role_str,
                "score": round(max(score, 10), 1),
                "capacity": capacity,
                "lead_time_days": lead_time,
                "past_disruptions": past_disruptions,
                "recommendation_level": "HIGHLY_RECOMMENDED" if score >= 80 else ("RECOMMENDED" if score >= 50 else "MODERATE")
            })

        # Sort descending by score
        scored_candidates.sort(key=lambda x: x["score"], reverse=True)
        return scored_candidates
