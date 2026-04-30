# Lab 2: Mzinga Evolution - REST API Security

## 1. Step A1: REST API Security & Communication Access Control

### 1.1 Goal
The primary objective of this step was to secure the Communications collection. In the previous lab, the database was accessed or updated with minimal restrictions via direct connection. We have now implemented a robust REST API Access Control layer using Payload CMS to ensure that only authenticated administrators can update communication records.

### 1.2 Code Changes
I updated the configuration in src/collections/Communications.ts to enforce administrative access across all operations (read, create, delete, update).

**File: src/collections/Communications.ts**

const Communications: CollectionConfig = {
  slug: Slugs.Communications,
  access: {
    read: access.GetIsAdmin,
    create: access.GetIsAdmin,
    delete: access.GetIsAdmin,
    update: access.GetIsAdmin,
  },
}

---

## 2. Verification Procedure

The implementation was verified through a series of manual REST API calls using curl to confirm that the security policy is correctly enforced.

### 2.1 Admin Authentication (Login)
First, I obtained a JWT token by authenticating as an admin.

**Command:**
curl -X POST http://localhost:3000/api/users/login -H "Content-Type: application/json" -d '{"email": "admin.lab1@example.com", "password": "Lab1Admin!2026"}'

**Outcome:**
The server returned 200 OK with a valid token. This proves the authentication system is correctly identifying administrative users.

### 2.2 Unauthorized Access Test (Security Check)
I attempted to update a communication status without providing the authorization token to verify the security lock.

**Command:**
curl -i -X PATCH http://localhost:3000/api/communications/69f335e7f5ca46e31034f72b -H "Content-Type: application/json" -d '{"status": "sent"}'

**Outcome:**
The server denied the request (Unauthorized), confirming that the Communications collection is now protected.

### 2.3 Authorized Update (Verification of Step A1)
Finally, I performed the update using the Bearer Token obtained in the first step.

**Command:**
curl -i -X PATCH http://localhost:3000/api/communications/69f335e7f5ca46e31034f72b -H "Authorization: Bearer <YOUR_JWT_TOKEN>" -H "Content-Type: application/json" -d '{"status": "sent"}'

**Final Result:**
The server responded with HTTP/1.1 200 OK. The JSON response confirmed the successful update:
- ID: 69f335e7f5ca46e31034f72b
- New Status: "sent"
- Updated At: 2026-04-30T13:16:23.410Z

This confirms that the access.GetIsAdmin rule is correctly implemented and enforces security for the entire collection.