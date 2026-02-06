export interface User {
    id: number;
    username: string;
    role: 'manager' | 'worker' | 'admin';
    personal_number: string;
    first_name: string;
    last_name: string;

}

export interface AuthResponse {
    token: string;
}

// Toto je formát, v akom backend posiela dáta o userovi
export interface CurrentUser {
    id: number;
    username: string;
    first_name: string;
    last_name: string;
    email?: string;
    role: 'admin' | 'manager' | 'worker';
}