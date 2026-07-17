# Travelly — Use Case: Input Travel Logistics

---

## Use Case Summary

| Field | Details |
|-------|---------|
| **Use Case Name** | Input Travel Logistics |
| **Actor(s)** | User, OpenStreetMap API |
| **Description** | Allows the user to configure the parameters of their trip, including the mandatory starting and ending geographic coordinates, departure time, group size, pricing identity, and an optional budget limit. |
| **Priority** | High |
| **Precondition(s)** | The user has opened the Travelly dashboard and initiated the "Start My Itinerary" flow. |
| **Post Condition(s)** | The core logistics are temporarily cached, and the user is allowed to proceed to the middle destinations setup. |

---

## Main Flow

| Step | Actor | Action |
|------|-------|--------|
| 1 | User | Inputs their Start and End points (geographic locations). |
| 2 | System | Queries the OpenStreetMap API to fetch real-time geographic coordinate suggestions. |
| 3 | User | Selects the verified locations from the autocomplete dropdown. |
| 4 | User | Sets the departure time, group size, pricing identity, and budget (optional). |
| 5 | System | Saves these parameters into the active session memory. |

---

## Alternative Flows

| Alt-ID | Condition | Steps |
|--------|-----------|-------|
| A1 | OpenStreetMap API returns no results | System displays "No location found" message; user retries with different search terms. |
| A2 | User skips optional budget field | System proceeds without budget constraint; no validation error. |
| A3 | Network failure during API call | System shows a retry prompt; cached previous suggestions shown if available. |

---

## Exception Flows

| Exc-ID | Condition | Response |
|--------|-----------|----------|
| E1 | OpenStreetMap API timeout (>5s) | System falls back to manual coordinate entry. |
| E2 | Invalid departure time (past date) | System highlights the field with an error: "Departure must be in the future." |
| E3 | Group size ≤ 0 | System rejects input with validation error. |

---

## Data Requirements

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| Start Point (coordinates) | lat/lng | Yes | Must be a valid geographic coordinate from OpenStreetMap. |
| End Point (coordinates) | lat/lng | Yes | Must be a valid geographic coordinate from OpenStreetMap. |
| Departure Time | DateTime | Yes | Must be a future date/time. |
| Group Size | Integer | Yes | Minimum 1. |
| Pricing Identity | String/Enum | Yes | One of: Budget, Standard, Premium. |
| Budget Limit | Decimal | No | Must be ≥ 0 if provided. |
