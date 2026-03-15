import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';

describe('DialogContent', () => {
  it('includes default animation classes by default', () => {
    render(
        <Dialog open>
        <DialogContent>
          <DialogTitle>Default dialog</DialogTitle>
          <DialogDescription>Default dialog description</DialogDescription>
          <div>Body</div>
        </DialogContent>
      </Dialog>,
    );

    const dialog = screen.getByRole('dialog');
    expect(dialog.className).toContain('data-[state=open]:slide-in-from-left-1/2');
    expect(dialog.className).toContain('data-[state=open]:zoom-in-95');
  });

  it('omits default animation classes when disabled', () => {
    render(
      <Dialog open>
        <DialogContent noDefaultAnimation className="inset-4 left-0 top-0 translate-x-0 translate-y-0">
          <DialogTitle>Fullscreen dialog</DialogTitle>
          <DialogDescription>Fullscreen dialog description</DialogDescription>
          <div>Body</div>
        </DialogContent>
      </Dialog>,
    );

    const dialog = screen.getByRole('dialog');
    expect(dialog.className).not.toContain('data-[state=open]:slide-in-from-left-1/2');
    expect(dialog.className).not.toContain('data-[state=open]:zoom-in-95');
    expect(dialog.className).toContain('inset-4');
  });
});
