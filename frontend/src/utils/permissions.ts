import type { UserRole } from '@/types';

type Permission =
  | 'manage_devices'
  | 'create_shipments'
  | 'manage_legs'
  | 'manage_checkpoints'
  | 'update_shipment_status';

const rolePermissions: Record<UserRole, Permission[]> = {
  admin: [
    'manage_devices',
    'create_shipments',
    'manage_legs',
    'manage_checkpoints',
    'update_shipment_status',
  ],
  factory: ['manage_devices', 'create_shipments', 'manage_legs', 'manage_checkpoints'],
  port: ['create_shipments', 'manage_legs', 'manage_checkpoints'],
  warehouse: ['create_shipments', 'manage_legs', 'manage_checkpoints'],
  customer: [],
  authority: ['manage_legs', 'manage_checkpoints', 'update_shipment_status'],
};

export function hasPermission(role: UserRole | undefined, permission: Permission): boolean {
  if (!role) {
    return false;
  }

  return rolePermissions[role]?.includes(permission) ?? false;
}
