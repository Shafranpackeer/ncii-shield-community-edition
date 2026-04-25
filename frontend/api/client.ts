import axios from 'axios';

const getApiBaseUrl = () => {
  if (typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:8001`;
  }

  return process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8001';
};

const API_BASE_URL = getApiBaseUrl();

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Types
export interface Case {
  id: number;
  victim_id: string;
  status: 'active' | 'resolved' | 'suspended';
  created_at: string;
  authorization_doc?: string;
}

export interface Identifier {
  type: 'name' | 'handle' | 'alias' | 'email' | 'phone';
  value: string;
}

export interface ReferenceHash {
  phash: number;
  dhash: number;
  face_embedding?: number[];
  label?: string;
}

export interface Target {
  id?: number;
  case_id?: number;
  url: string;
  status?: string;
  discovery_source?: string;
  confidence_score?: number;
  next_action_at?: string;
  created_at?: string;
  updated_at?: string;
}

export interface Contact {
  id: number;
  target_id: number;
  email: string;
  method_found?: string;
  confidence?: number;
  created_at: string;
}

export interface Action {
  id: number;
  target_id: number;
  type: string;
  payload?: any;
  status: string;
  scheduled_at?: string;
  executed_at?: string;
  created_at: string;
  created_by?: string;
  error_message?: string;
}

export interface AuditEntry {
  id: number;
  entity_type: string;
  entity_id: number;
  action: string;
  old_value?: any;
  new_value?: any;
  user_id?: string;
  created_at: string;
}

export interface RuntimeSetting {
  key: string;
  label: string;
  description: string;
  category: string;
  docs_url?: string | null;
  secret: boolean;
  placeholder?: string | null;
  value: string;
  updated_at?: string | null;
}

// API methods
export const casesAPI = {
  create: async (data: { victim_id: string; authorization_doc?: string }) => {
    const response = await apiClient.post<Case>('/cases/', data);
    return response.data;
  },

  list: async () => {
    const response = await apiClient.get<{ cases: Case[]; total: number }>('/cases/');
    return response.data;
  },

  get: async (id: number) => {
    const response = await apiClient.get<Case>(`/cases/${id}`);
    return response.data;
  },

  addIdentifier: async (caseId: number, data: Identifier) => {
    const response = await apiClient.post(`/cases/${caseId}/identifiers`, data);
    return response.data;
  },

  addReferenceHash: async (caseId: number, data: ReferenceHash) => {
    const response = await apiClient.post(`/cases/${caseId}/reference-hashes`, data);
    return response.data;
  },

  addTarget: async (caseId: number, data: Target) => {
    const response = await apiClient.post(`/cases/${caseId}/targets`, data);
    return response.data;
  },
};

export const operationsAPI = {
  resolveContact: async (targetId: number) => {
    const response = await apiClient.post<Contact>(`/operations/targets/${targetId}/resolve-contact`);
    return response.data;
  },

  addContact: async (targetId: number, data: { email: string; method_found?: string; confidence?: number }) => {
    const response = await apiClient.post<Contact>(`/operations/targets/${targetId}/contacts`, data);
    return response.data;
  },

  createDraft: async (targetId: number, data: { action_type?: string; jurisdiction?: string }) => {
    const response = await apiClient.post<Action>(`/operations/targets/${targetId}/draft`, data);
    return response.data;
  },

  listActions: async (caseId: number) => {
    const response = await apiClient.get<Action[]>(`/operations/cases/${caseId}/actions`);
    return response.data;
  },

  reviewAction: async (actionId: number, data: { decision: 'approve' | 'reject'; edited_subject?: string; edited_body?: string; admin_id?: string }) => {
    const response = await apiClient.post<Action>(`/operations/actions/${actionId}/review`, data);
    return response.data;
  },

  killSwitch: async (caseId: number) => {
    const response = await apiClient.post(`/operations/cases/${caseId}/kill-switch`);
    return response.data;
  },

  resolveCase: async (caseId: number) => {
    const response = await apiClient.post(`/operations/cases/${caseId}/resolve`);
    return response.data;
  },

  timeline: async (caseId: number) => {
    const response = await apiClient.get<AuditEntry[]>(`/operations/cases/${caseId}/timeline`);
    return response.data;
  },

  checkTargetAlive: async (targetId: number) => {
    const response = await apiClient.post(`/operations/targets/${targetId}/check-alive`);
    return response.data;
  },

  checkCaseLinks: async (caseId: number) => {
    const response = await apiClient.post(`/operations/cases/${caseId}/check-links`);
    return response.data;
  },
};

// Discovery API methods
export const discoveryAPI = {
  triggerDiscovery: async (caseId: number, adminApproved: boolean = false) => {
    const response = await apiClient.post(`/discovery/cases/${caseId}/run`, null, {
      params: { admin_approved: adminApproved }
    });
    return response.data;
  },

  previewDiscovery: async (caseId: number, adminApproved: boolean = true) => {
    const response = await apiClient.get(`/discovery/cases/${caseId}/preview`, {
      params: { admin_approved: adminApproved }
    });
    return response.data;
  },

  runManualScan: async (caseId: number, adminApproved: boolean = true) => {
    const response = await apiClient.post(`/discovery/cases/${caseId}/run-sync`, null, {
      params: { admin_approved: adminApproved },
      timeout: 300000,
    });
    return response.data;
  },

  scanProgress: async (caseId: number) => {
    const response = await apiClient.get(`/discovery/cases/${caseId}/progress`);
    return response.data;
  },

  getTargets: async (caseId: number, status?: string) => {
    const response = await apiClient.get<Target[]>(`/discovery/cases/${caseId}/targets`, {
      params: status ? { status } : {}
    });
    return response.data;
  },

  reviewTarget: async (targetId: number, action: 'approve' | 'reject') => {
    const response = await apiClient.post(`/discovery/targets/${targetId}/review`, null, {
      params: { action }
    });
    return response.data;
  },

  bulkReviewTargets: async (targetIds: number[], action: 'approve' | 'reject') => {
    const response = await apiClient.post('/discovery/targets/bulk-review', {
      target_ids: targetIds,
      action
    });
    return response.data;
  },

  getStats: async (caseId: number) => {
    const response = await apiClient.get(`/discovery/stats/${caseId}`);
    return response.data;
  }
};

export const configAPI = {
  listSettings: async () => {
    const response = await apiClient.get<{ settings: RuntimeSetting[] }>('/config/settings');
    return response.data;
  },

  saveSettings: async (settings: Array<{ key: string; value: string }>) => {
    const response = await apiClient.post<{ settings: RuntimeSetting[] }>('/config/settings', { settings });
    return response.data;
  },
};
