export interface EmployeePayload {
    id?: number;
    username: string;
    first_name: string;
    last_name: string;
    email: string;
    personal_number: string;
    role: 'admin' | 'manager' | 'worker';
    initial_hours_balance?: number;
    password?: string;
    is_active?: boolean; // 👈 PRIDANÉ
}