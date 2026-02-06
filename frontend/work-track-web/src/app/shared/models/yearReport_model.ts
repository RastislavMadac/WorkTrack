export interface YearlyStats {
    so: number; ne: number; sv: number; noc: number; den: number; pn: number;
}

export interface HolidayRecord {
    user_id: number;
    hours: number;
}

export interface HolidaySummary {
    date: string;
    name: string;
    records: HolidayRecord[];
}

export interface YearlyReportResponse {
    year: number;
    employees: { id: number; name: string }[];

    // Matica: Key je ID zamestnanca -> Value je objekt s dátami
    matrix: {
        [userId: number]: {
            name: string;
            data: {
                [month: number]: YearlyStats; // Pre mesiace 1-12
                total?: YearlyStats;          // <--- TOTO JE DÔLEŽITÉ PRIDAŤ (aby fungoval riadok SPOLU)
            }
        }
    };

    holidays_current: HolidaySummary[];
    holidays_prev: HolidaySummary[];
}