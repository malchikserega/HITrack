def resolve_repository_tag_processing_status(
    current_status,
    total_images,
    pending_images,
    in_process_images,
    error_images,
    success_images,
):
    current_status = current_status or 'none'

    if total_images == 0:
        return current_status

    if current_status == 'pending' and pending_images > 0 and in_process_images == 0:
        return 'pending'

    if pending_images > 0 or in_process_images > 0:
        return 'in_process'

    if error_images > 0:
        return 'error'

    if success_images == total_images:
        return 'success'

    if current_status in ['pending', 'in_process']:
        return 'in_process'

    return current_status


def resolve_repository_scan_status(
    current_status,
    active_tag_count,
    active_image_count,
):
    current_status = current_status or 'none'

    if current_status == 'pending' and active_tag_count == 0 and active_image_count == 0:
        return 'pending'

    if current_status == 'in_process':
        return 'in_process'

    if active_tag_count > 0 or active_image_count > 0:
        return 'in_process'

    return current_status
