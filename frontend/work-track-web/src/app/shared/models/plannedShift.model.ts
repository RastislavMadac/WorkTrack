import { TypeShift } from "./typeShift.model";



export interface PlannedShift {
    id?: number;
    user: number; // ID zamestnanca
    date: string; // YYYY-MM-DD
    type_shift: number | TypeShift; // ID pri POST, Objekt pri GET
    custom_start?: string;
    custom_end?: string;
    note?: string;
    // Stavové polia
    transferred?: boolean;    // Či už je v dochádzke
    is_changed?: boolean;
    hidden?: boolean;         // Soft delete

    // Ostatné väzby
    change_reason?: number | null;
    calendar_day?: number | null;

    approval_status?: 'pending' | 'approved' | 'rejected'; // Status schválenia
    exchange_link?: number | null; // ID pôvodnej smeny (pri výmene)
    manager_note?: string; // Poznámka manažéra pri schválení/zamietnutí
    target_user_id?: number; // Len pre frontend: ID kolegu pri žiadosti o výmenu

    // --- Read-only polia (ktoré posiela Serializer navyše) ---
    shift_name?: string;      // napr. "Ranná zmena"
    short_name?: string;      // napr. "R"
    duration?: string;        // napr. "08:00"
}


export interface MonthlySummary {
    user_id: number;
    prevBalance: number; // Prenesené z minula (počiatočný stav)
    fund: number;        // Fond pracovného času
    worked: number;      // Odpracované
    diff: number;        // Rozdiel (Odpracované - Fond)
    total: number;       // Výsledný stav (Prenesené + Rozdiel)
    night: number;
    weekend: number;
    holiday: number;
}

