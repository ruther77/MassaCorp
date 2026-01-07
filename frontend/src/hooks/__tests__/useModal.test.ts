import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useModal, useMultiModal, useConfirmModal } from '../useModal';

describe('useModal', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should initialize with closed state', () => {
    const { result } = renderHook(() => useModal());

    expect(result.current.isOpen).toBe(false);
    expect(result.current.data).toBeNull();
  });

  it('should initialize with open state when initialOpen is true', () => {
    const { result } = renderHook(() => useModal(true));

    expect(result.current.isOpen).toBe(true);
  });

  it('should open modal without data', () => {
    const { result } = renderHook(() => useModal());

    act(() => {
      result.current.open();
    });

    expect(result.current.isOpen).toBe(true);
    expect(result.current.data).toBeNull();
  });

  it('should open modal with data', () => {
    const { result } = renderHook(() => useModal<{ id: number }>());
    const testData = { id: 123 };

    act(() => {
      result.current.open(testData);
    });

    expect(result.current.isOpen).toBe(true);
    expect(result.current.data).toEqual(testData);
  });

  it('should close modal and reset data after delay', () => {
    const { result } = renderHook(() => useModal<{ id: number }>());

    act(() => {
      result.current.open({ id: 123 });
    });

    expect(result.current.isOpen).toBe(true);

    act(() => {
      result.current.close();
    });

    expect(result.current.isOpen).toBe(false);
    // Data should still exist until timeout
    expect(result.current.data).toEqual({ id: 123 });

    // Fast-forward timer
    act(() => {
      vi.advanceTimersByTime(200);
    });

    expect(result.current.data).toBeNull();
  });

  it('should toggle modal state', () => {
    const { result } = renderHook(() => useModal());

    expect(result.current.isOpen).toBe(false);

    act(() => {
      result.current.toggle();
    });

    expect(result.current.isOpen).toBe(true);

    act(() => {
      result.current.toggle();
    });

    expect(result.current.isOpen).toBe(false);
  });
});

describe('useMultiModal', () => {
  it('should initialize with no active modal', () => {
    const { result } = renderHook(() => useMultiModal());

    expect(result.current.activeModal).toBeNull();
    expect(result.current.data).toBeNull();
  });

  it('should open specific modal by id', () => {
    const { result } = renderHook(() => useMultiModal());

    act(() => {
      result.current.open('edit');
    });

    expect(result.current.activeModal).toBe('edit');
    expect(result.current.isOpen('edit')).toBe(true);
    expect(result.current.isOpen('delete')).toBe(false);
  });

  it('should open modal with data', () => {
    const { result } = renderHook(() => useMultiModal<{ userId: number }>());

    act(() => {
      result.current.open('edit', { userId: 42 });
    });

    expect(result.current.activeModal).toBe('edit');
    expect(result.current.data).toEqual({ userId: 42 });
  });

  it('should switch between modals', () => {
    const { result } = renderHook(() => useMultiModal());

    act(() => {
      result.current.open('create');
    });

    expect(result.current.isOpen('create')).toBe(true);

    act(() => {
      result.current.open('edit');
    });

    expect(result.current.isOpen('create')).toBe(false);
    expect(result.current.isOpen('edit')).toBe(true);
  });

  it('should close all modals', () => {
    const { result } = renderHook(() => useMultiModal());

    act(() => {
      result.current.open('delete');
    });

    act(() => {
      result.current.close();
    });

    expect(result.current.activeModal).toBeNull();
    expect(result.current.data).toBeNull();
  });

  it('should toggle modal - open if closed', () => {
    const { result } = renderHook(() => useMultiModal());

    act(() => {
      result.current.toggle('create');
    });

    expect(result.current.isOpen('create')).toBe(true);
  });

  it('should toggle modal - close if same modal is open', () => {
    const { result } = renderHook(() => useMultiModal());

    act(() => {
      result.current.open('create');
    });

    act(() => {
      result.current.toggle('create');
    });

    expect(result.current.activeModal).toBeNull();
  });

  it('should toggle modal - switch to new modal if different is open', () => {
    const { result } = renderHook(() => useMultiModal());

    act(() => {
      result.current.open('create');
    });

    act(() => {
      result.current.toggle('edit');
    });

    expect(result.current.isOpen('edit')).toBe(true);
    expect(result.current.isOpen('create')).toBe(false);
  });
});

describe('useConfirmModal', () => {
  it('should initialize with closed state', () => {
    const { result } = renderHook(() => useConfirmModal());

    expect(result.current.isOpen).toBe(false);
    expect(result.current.data).toBeNull();
  });

  it('should open modal and return promise', async () => {
    const { result } = renderHook(() => useConfirmModal());

    let confirmPromise: Promise<boolean>;

    act(() => {
      confirmPromise = result.current.confirm();
    });

    expect(result.current.isOpen).toBe(true);
    expect(confirmPromise!).toBeInstanceOf(Promise);
  });

  it('should resolve true when confirmed', async () => {
    const { result } = renderHook(() => useConfirmModal());

    let confirmPromise: Promise<boolean>;

    act(() => {
      confirmPromise = result.current.confirm();
    });

    act(() => {
      result.current.handleConfirm();
    });

    const confirmed = await confirmPromise!;
    expect(confirmed).toBe(true);
    expect(result.current.isOpen).toBe(false);
  });

  it('should resolve false when cancelled', async () => {
    const { result } = renderHook(() => useConfirmModal());

    let confirmPromise: Promise<boolean>;

    act(() => {
      confirmPromise = result.current.confirm();
    });

    act(() => {
      result.current.handleCancel();
    });

    const confirmed = await confirmPromise!;
    expect(confirmed).toBe(false);
    expect(result.current.isOpen).toBe(false);
  });

  it('should pass data to modal', () => {
    const { result } = renderHook(() => useConfirmModal<{ itemName: string }>());

    act(() => {
      result.current.confirm({ itemName: 'Test Item' });
    });

    expect(result.current.data).toEqual({ itemName: 'Test Item' });
  });
});
