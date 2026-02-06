import { TypeShift } from "./typeShift.model";
import { PlannedShift } from "./plannedShift.model";

export interface AttendancePayload {
    id?: number;
    user: number;
    employee_name?: string;
    date: string; // YYYY-MM-DD
    type_shift?: number;
    shift_name?: string;
    shift_short?: string;
    planned_shift?: number | null; // ID plánovanej smeny
    custom_start?: string; // HH:mm
    custom_end?: string;   // HH:mm
    note?: string;
    change_reason_id?: number | null; // Backend vyžaduje ID
}