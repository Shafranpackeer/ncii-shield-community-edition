const ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';

const hashInput = (input: string): number => {
  let hash = 2166136261;
  for (let index = 0; index < input.length; index += 1) {
    hash ^= input.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
};

const encodeReference = (value: number, length = 8): string => {
  let output = '';
  let current = value || 1;
  for (let index = 0; index < length; index += 1) {
    output += ALPHABET[current % ALPHABET.length];
    current = Math.floor(current / ALPHABET.length) || hashInput(`${value}-${index}`);
  }
  return output;
};

export const formatCaseReference = (caseId?: number | null, createdAt?: string): string => {
  if (!caseId) {
    return 'NCII-PENDING';
  }

  const date = createdAt ? new Date(createdAt) : new Date();
  const year = Number.isNaN(date.getTime()) ? new Date().getFullYear() : date.getFullYear();
  const month = Number.isNaN(date.getTime()) ? new Date().getMonth() + 1 : date.getMonth() + 1;
  const period = `${year}${String(month).padStart(2, '0')}`;
  const suffix = encodeReference(hashInput(`${period}-${caseId}`));

  return `NCII-${period}-${suffix}`;
};
