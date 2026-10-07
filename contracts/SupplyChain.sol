// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * @title SupplyChain
 * @dev Decentralized Supply Chain Management System with Disruption Detection and Recovery
 */
contract SupplyChain {

    enum Role { NONE, ADMIN, SUPPLIER, MANUFACTURER, DISTRIBUTOR, RETAILER, CONSUMER }
    enum UserStatus { PENDING, APPROVED, REJECTED }
    enum OrderStatus { CREATED, WITH_MANUFACTURER, SUPPLIER_ASSIGNED, IN_PRODUCTION, DISTRIBUTOR_ASSIGNED, RETAILER_ASSIGNED, SHIPPED, DELIVERED, DISRUPTED }
    enum LegStatus { NOT_STARTED, PREPARING, SHIPPED, IN_TRANSIT, DELAYED, DELIVERED, DISRUPTED }
    enum LegType { LEG1_SUPPLIER_TO_MFG, LEG2_MFG_TO_DISTRIBUTOR, LEG3_DISTRIBUTOR_TO_RETAILER, LEG4_RETAILER_TO_CONSUMER }

    struct Participant {
        string username;
        Role role;
        string email;
        address ethAddress;
        UserStatus status;
        uint256 registrationTime;
    }

    struct Material {
        string id;
        string name;
        string category;
        uint256 capacity;
        uint256 leadTimeDays;
        address supplierAddress;
        string status;
        string documentIpfsHash;
        uint256 createdAt;
    }

    struct Product {
        string id;
        string name;
        string category;
        uint256 price;
        address manufacturerAddress;
        string[] requiredMaterialIds;
        uint256 createdAt;
    }

    struct Dependency {
        string id;
        string orderId;
        string materialId;
        address supplierAddress;
        address manufacturerAddress;
        address distributorAddress;
        address retailerAddress;
        uint256 timestamp;
    }

    struct ShipmentLeg {
        string legId;
        string orderId;
        LegType legType;
        address fromAddress;
        address toAddress;
        LegStatus status;
        uint256 expectedDate;
        uint256 actualDate;
        uint256 lastUpdated;
        string documentHash;
        string notes;
    }

    struct Order {
        string orderId;
        address consumerAddress;
        string productId;
        uint256 quantity;
        uint256 expectedDeliveryDate;
        address manufacturerAddress;
        address supplierAddress;
        address distributorAddress;
        address retailerAddress;
        OrderStatus status;
        uint256 createdAt;
        string documentIpfsHash;
    }

    struct Disruption {
        string disruptionId;
        string orderId;
        string legId;
        address reportedBy;
        address participantAddress;
        string disruptionType;
        string description;
        uint256 timestamp;
        bool resolved;
    }

    struct RoleSwitch {
        string switchId;
        string orderId;
        string legId;
        address oldParticipant;
        address newParticipant;
        Role role;
        string reason;
        uint256 timestamp;
    }

    // Storage Mappings
    mapping(address => Participant) public participants;
    address[] public participantAddresses;

    mapping(string => Material) public materials;
    string[] public materialIds;

    mapping(string => Product) public products;
    string[] public productIds;

    mapping(string => Dependency) public dependencies;
    string[] public dependencyIds;

    mapping(string => Order) public orders;
    string[] public orderIds;

    mapping(string => ShipmentLeg) public shipmentLegs;
    string[] public shipmentLegIds;

    // Mapping orderId => array of legIds
    mapping(string => string[]) public orderLegs;

    mapping(string => Disruption) public disruptions;
    string[] public disruptionIds;

    mapping(string => RoleSwitch) public roleSwitches;
    string[] public roleSwitchIds;

    address public adminAddress;

    // Events
    event ParticipantRegistered(address indexed ethAddress, string username, Role role, UserStatus status);
    event ParticipantApproved(address indexed ethAddress, Role role);
    event ParticipantRejected(address indexed ethAddress);
    event MaterialSaved(string id, string name, address indexed supplier);
    event ProductSaved(string id, string name, address indexed manufacturer);
    event OrderCreated(string indexed orderId, address indexed consumer, address indexed manufacturer);
    event SupplierAndDistributorAssigned(string indexed orderId, address supplier, address distributor);
    event RetailerAssigned(string indexed orderId, address retailer);
    event DependencySaved(string id, string orderId);
    event ShipmentLegCreated(string legId, string orderId, LegType legType);
    event ShipmentLegStatusUpdated(string legId, LegStatus status, uint256 timestamp);
    event DisruptionRecorded(string disruptionId, string orderId, string legId, string disruptionType);
    event RoleSwitched(string switchId, string orderId, address oldParticipant, address newParticipant, Role role);

    modifier onlyAdmin() {
        require(msg.sender == adminAddress || participants[msg.sender].role == Role.ADMIN, "Only Admin allowed");
        _;
    }

    modifier onlyApproved() {
        require(participants[msg.sender].status == UserStatus.APPROVED, "User not approved");
        _;
    }

    constructor() {
        // Contract Deployer defaults to initial admin
        adminAddress = msg.sender;
        participants[msg.sender] = Participant({
            username: "DefaultAdmin",
            role: Role.ADMIN,
            email: "admin@supplychain.eth",
            ethAddress: msg.sender,
            status: UserStatus.APPROVED,
            registrationTime: block.timestamp
        });
        participantAddresses.push(msg.sender);
    }

    // --- REGISTRATION & USER MANAGEMENT ---

    function saveAdmin(string memory username, string memory email) public {
        require(adminAddress == address(0) || msg.sender == adminAddress || participantAddresses.length == 0, "Admin already set");
        adminAddress = msg.sender;
        participants[msg.sender] = Participant({
            username: username,
            role: Role.ADMIN,
            email: email,
            ethAddress: msg.sender,
            status: UserStatus.APPROVED,
            registrationTime: block.timestamp
        });
        participantAddresses.push(msg.sender);
        emit ParticipantRegistered(msg.sender, username, Role.ADMIN, UserStatus.APPROVED);
    }

    function _registerParticipant(string memory username, string memory email, Role role) internal {
        require(participants[msg.sender].role == Role.NONE, "User already registered");
        participants[msg.sender] = Participant({
            username: username,
            role: role,
            email: email,
            ethAddress: msg.sender,
            status: UserStatus.PENDING,
            registrationTime: block.timestamp
        });
        participantAddresses.push(msg.sender);
        emit ParticipantRegistered(msg.sender, username, role, UserStatus.PENDING);
    }

    function saveSupplier(string memory username, string memory email) public {
        _registerParticipant(username, email, Role.SUPPLIER);
    }

    function saveManufacturer(string memory username, string memory email) public {
        _registerParticipant(username, email, Role.MANUFACTURER);
    }

    function saveDistributor(string memory username, string memory email) public {
        _registerParticipant(username, email, Role.DISTRIBUTOR);
    }

    function saveRetailer(string memory username, string memory email) public {
        _registerParticipant(username, email, Role.RETAILER);
    }

    function saveConsumer(string memory username, string memory email) public {
        _registerParticipant(username, email, Role.CONSUMER);
    }

    function approveUser(address userAddr) public onlyAdmin {
        require(participants[userAddr].role != Role.NONE, "Participant does not exist");
        participants[userAddr].status = UserStatus.APPROVED;
        emit ParticipantApproved(userAddr, participants[userAddr].role);
    }

    function rejectUser(address userAddr) public onlyAdmin {
        require(participants[userAddr].role != Role.NONE, "Participant does not exist");
        participants[userAddr].status = UserStatus.REJECTED;
        emit ParticipantRejected(userAddr);
    }

    // --- MATERIALS & PRODUCTS ---

    function saveMaterial(
        string memory id,
        string memory name,
        string memory category,
        uint256 capacity,
        uint256 leadTimeDays,
        string memory documentIpfsHash
    ) public onlyApproved {
        require(participants[msg.sender].role == Role.SUPPLIER, "Only Supplier can save material");
        materials[id] = Material({
            id: id,
            name: name,
            category: category,
            capacity: capacity,
            leadTimeDays: leadTimeDays,
            supplierAddress: msg.sender,
            status: "AVAILABLE",
            documentIpfsHash: documentIpfsHash,
            createdAt: block.timestamp
        });
        materialIds.push(id);
        emit MaterialSaved(id, name, msg.sender);
    }

    function saveProduct(
        string memory id,
        string memory name,
        string memory category,
        uint256 price,
        string[] memory requiredMaterialIds
    ) public onlyApproved {
        require(participants[msg.sender].role == Role.MANUFACTURER, "Only Manufacturer can save product");
        products[id] = Product({
            id: id,
            name: name,
            category: category,
            price: price,
            manufacturerAddress: msg.sender,
            requiredMaterialIds: requiredMaterialIds,
            createdAt: block.timestamp
        });
        productIds.push(id);
        emit ProductSaved(id, name, msg.sender);
    }

    // --- ORDERS & DEPENDENCIES ---

    function createOrder(
        string memory orderId,
        string memory productId,
        uint256 quantity,
        uint256 expectedDeliveryDate,
        string memory documentIpfsHash
    ) public onlyApproved {
        require(participants[msg.sender].role == Role.CONSUMER, "Only Consumer can place order");
        require(bytes(products[productId].id).length > 0, "Product does not exist");

        address mfgAddr = products[productId].manufacturerAddress;

        orders[orderId] = Order({
            orderId: orderId,
            consumerAddress: msg.sender,
            productId: productId,
            quantity: quantity,
            expectedDeliveryDate: expectedDeliveryDate,
            manufacturerAddress: mfgAddr,
            supplierAddress: address(0),
            distributorAddress: address(0),
            retailerAddress: address(0),
            status: OrderStatus.WITH_MANUFACTURER,
            createdAt: block.timestamp,
            documentIpfsHash: documentIpfsHash
        });
        orderIds.push(orderId);
        emit OrderCreated(orderId, msg.sender, mfgAddr);
    }

    function assignSupplierAndDistributor(
        string memory orderId,
        address supplierAddr,
        address distributorAddr
    ) public onlyApproved {
        Order storage ord = orders[orderId];
        require(ord.manufacturerAddress == msg.sender, "Only assigned Manufacturer can update");
        ord.supplierAddress = supplierAddr;
        ord.distributorAddress = distributorAddr;
        ord.status = OrderStatus.SUPPLIER_ASSIGNED;
        emit SupplierAndDistributorAssigned(orderId, supplierAddr, distributorAddr);
    }

    function assignRetailer(
        string memory orderId,
        address retailerAddr
    ) public onlyApproved {
        Order storage ord = orders[orderId];
        require(ord.distributorAddress == msg.sender, "Only assigned Distributor can assign Retailer");
        ord.retailerAddress = retailerAddr;
        ord.status = OrderStatus.RETAILER_ASSIGNED;
        emit RetailerAssigned(orderId, retailerAddr);
    }

    function saveDependency(
        string memory id,
        string memory orderId,
        string memory materialId,
        address supplierAddr,
        address manufacturerAddr,
        address distributorAddr,
        address retailerAddr
    ) public onlyApproved {
        dependencies[id] = Dependency({
            id: id,
            orderId: orderId,
            materialId: materialId,
            supplierAddress: supplierAddr,
            manufacturerAddress: manufacturerAddr,
            distributorAddress: distributorAddr,
            retailerAddress: retailerAddr,
            timestamp: block.timestamp
        });
        dependencyIds.push(id);
        emit DependencySaved(id, orderId);
    }

    // --- SHIPMENT LEGS ---

    function createShipmentLeg(
        string memory legId,
        string memory orderId,
        LegType legType,
        address fromAddr,
        address toAddr,
        uint256 expectedDate,
        string memory documentHash,
        string memory notes
    ) public onlyApproved {
        shipmentLegs[legId] = ShipmentLeg({
            legId: legId,
            orderId: orderId,
            legType: legType,
            fromAddress: fromAddr,
            toAddress: toAddr,
            status: LegStatus.PREPARING,
            expectedDate: expectedDate,
            actualDate: 0,
            lastUpdated: block.timestamp,
            documentHash: documentHash,
            notes: notes
        });
        shipmentLegIds.push(legId);
        orderLegs[orderId].push(legId);
        emit ShipmentLegCreated(legId, orderId, legType);
    }

    function updateShipmentLegStatus(
        string memory legId,
        LegStatus status,
        string memory documentHash,
        string memory notes
    ) public onlyApproved {
        ShipmentLeg storage leg = shipmentLegs[legId];
        require(bytes(leg.legId).length > 0, "Leg does not exist");

        leg.status = status;
        leg.lastUpdated = block.timestamp;
        if (bytes(documentHash).length > 0) {
            leg.documentHash = documentHash;
        }
        if (bytes(notes).length > 0) {
            leg.notes = notes;
        }

        if (status == LegStatus.DELIVERED) {
            leg.actualDate = block.timestamp;
            // Update order overall status if leg 4 delivered
            if (leg.legType == LegType.LEG4_RETAILER_TO_CONSUMER) {
                orders[leg.orderId].status = OrderStatus.DELIVERED;
            }
        } else if (status == LegStatus.SHIPPED || status == LegStatus.IN_TRANSIT) {
            orders[leg.orderId].status = OrderStatus.SHIPPED;
        } else if (status == LegStatus.DELAYED || status == LegStatus.DISRUPTED) {
            orders[leg.orderId].status = OrderStatus.DISRUPTED;
        }

        emit ShipmentLegStatusUpdated(legId, status, block.timestamp);
    }

    // --- DISRUPTIONS & ROLE SWITCHES ---

    function recordDisruption(
        string memory disruptionId,
        string memory orderId,
        string memory legId,
        address participantAddr,
        string memory disruptionType,
        string memory description
    ) public onlyApproved {
        disruptions[disruptionId] = Disruption({
            disruptionId: disruptionId,
            orderId: orderId,
            legId: legId,
            reportedBy: msg.sender,
            participantAddress: participantAddr,
            disruptionType: disruptionType,
            description: description,
            timestamp: block.timestamp,
            resolved: false
        });
        disruptionIds.push(disruptionId);

        orders[orderId].status = OrderStatus.DISRUPTED;
        if (bytes(legId).length > 0) {
            shipmentLegs[legId].status = LegStatus.DISRUPTED;
        }

        emit DisruptionRecorded(disruptionId, orderId, legId, disruptionType);
    }

    function updateOrderSupplier(
        string memory orderId,
        address newSupplierAddr,
        string memory reason
    ) public onlyApproved {
        Order storage ord = orders[orderId];
        address oldSupplier = ord.supplierAddress;
        ord.supplierAddress = newSupplierAddr;

        string memory switchId = string(abi.encodePacked("SW-SUP-", orderId, "-", _uintToStr(block.timestamp)));
        roleSwitches[switchId] = RoleSwitch({
            switchId: switchId,
            orderId: orderId,
            legId: "LEG1",
            oldParticipant: oldSupplier,
            newParticipant: newSupplierAddr,
            role: Role.SUPPLIER,
            reason: reason,
            timestamp: block.timestamp
        });
        roleSwitchIds.push(switchId);

        emit RoleSwitched(switchId, orderId, oldSupplier, newSupplierAddr, Role.SUPPLIER);
    }

    function updateOrderDistributor(
        string memory orderId,
        address newDistributorAddr,
        string memory reason
    ) public onlyApproved {
        Order storage ord = orders[orderId];
        address oldDistributor = ord.distributorAddress;
        ord.distributorAddress = newDistributorAddr;

        string memory switchId = string(abi.encodePacked("SW-DST-", orderId, "-", _uintToStr(block.timestamp)));
        roleSwitches[switchId] = RoleSwitch({
            switchId: switchId,
            orderId: orderId,
            legId: "LEG2",
            oldParticipant: oldDistributor,
            newParticipant: newDistributorAddr,
            role: Role.DISTRIBUTOR,
            reason: reason,
            timestamp: block.timestamp
        });
        roleSwitchIds.push(switchId);

        emit RoleSwitched(switchId, orderId, oldDistributor, newDistributorAddr, Role.DISTRIBUTOR);
    }

    function updateOrderRetailer(
        string memory orderId,
        address newRetailerAddr,
        string memory reason
    ) public onlyApproved {
        Order storage ord = orders[orderId];
        address oldRetailer = ord.retailerAddress;
        ord.retailerAddress = newRetailerAddr;

        string memory switchId = string(abi.encodePacked("SW-RET-", orderId, "-", _uintToStr(block.timestamp)));
        roleSwitches[switchId] = RoleSwitch({
            switchId: switchId,
            orderId: orderId,
            legId: "LEG3",
            oldParticipant: oldRetailer,
            newParticipant: newRetailerAddr,
            role: Role.RETAILER,
            reason: reason,
            timestamp: block.timestamp
        });
        roleSwitchIds.push(switchId);

        emit RoleSwitched(switchId, orderId, oldRetailer, newRetailerAddr, Role.RETAILER);
    }

    // --- GETTERS & COUNTS ---

    function getParticipantCount() public view returns (uint256) {
        return participantAddresses.length;
    }

    function getOrderCount() public view returns (uint256) {
        return orderIds.length;
    }

    function getShipmentLegCount() public view returns (uint256) {
        return shipmentLegIds.length;
    }

    function getDisruptionCount() public view returns (uint256) {
        return disruptionIds.length;
    }

    function getRoleSwitchCount() public view returns (uint256) {
        return roleSwitchIds.length;
    }

    function getProductRequiredMaterials(string memory productId) public view returns (string[] memory) {
        return products[productId].requiredMaterialIds;
    }

    function getOrderLegIds(string memory orderId) public view returns (string[] memory) {
        return orderLegs[orderId];
    }

    function _uintToStr(uint256 _i) internal pure returns (string memory _uintAsString) {
        if (_i == 0) {
            return "0";
        }
        uint256 j = _i;
        uint256 len;
        while (j != 0) {
            len++;
            j /= 10;
        }
        bytes memory bstr = new bytes(len);
        uint256 k = len;
        while (_i != 0) {
            k = k - 1;
            uint8 temp = (uint8)(48 + _i % 10);
            bytes1 b1 = bytes1(temp);
            bstr[k] = b1;
            _i /= 10;
        }
        return string(bstr);
    }
}
