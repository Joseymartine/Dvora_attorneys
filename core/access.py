def is_administrator(user):
    return user.is_superuser or user.groups.filter(name='Administrators').exists()


def is_lawyer(user):
    return user.groups.filter(name='Lawyers').exists()


def accessible_clients(user, queryset):
    if not user.is_authenticated or not user.is_active:
        return queryset.none()
    if is_administrator(user):
        return queryset
    if is_lawyer(user):
        return queryset.filter(cases__assigned_lawyer=user).distinct()
    return queryset.none()


def accessible_cases(user, queryset):
    if not user.is_authenticated or not user.is_active:
        return queryset.none()
    if is_administrator(user):
        return queryset
    if is_lawyer(user):
        return queryset.filter(assigned_lawyer=user)
    return queryset.none()


def accessible_appointments(user, queryset):
    if not user.is_authenticated or not user.is_active:
        return queryset.none()
    if is_administrator(user):
        return queryset
    if is_lawyer(user):
        return queryset.filter(assigned_lawyer=user)
    if user.groups.filter(name='Clients').exists():
        return queryset.filter(client__user=user)
    return queryset.none()
