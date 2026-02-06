import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AttendanceForm } from './attendance-form';

describe('AttendanceForm', () => {
  let component: AttendanceForm;
  let fixture: ComponentFixture<AttendanceForm>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AttendanceForm]
    })
    .compileComponents();

    fixture = TestBed.createComponent(AttendanceForm);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
