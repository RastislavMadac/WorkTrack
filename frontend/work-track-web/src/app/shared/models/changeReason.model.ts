export interface ChangeReason {
    id: number;
    name: string;
    description?: string;
    category: 'absence' | 'cdr';
}