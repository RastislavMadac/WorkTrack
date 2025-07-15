# def reset_auto_changed_attendance():
#     auto_records = PlannedShifts.objects.filter(
#         user=user,
#         date=date,
#         hidden=False,
#         is_changed=True,
#         note__icontains="Chýbajúca dochádzka k plánovanej smene"
#     )
#     updated_count = auto_records.update(is_changed=False, note="")


#     print(f"Resetovaných {updated_count} automatických záznamov plánovaných smien.")