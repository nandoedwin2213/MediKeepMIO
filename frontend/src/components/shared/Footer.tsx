/**
 * Footer - Shared footer component
 * Displays the clinic copyright and credits the upstream MediKeep project.
 */

import React from 'react';
import { Box, Text, Anchor, Group } from '@mantine/core';
import { IconBrandGithub } from '@tabler/icons-react';
import { BRAND } from '../../config/brand';

interface FooterProps {
  className?: string;
}

const Footer: React.FC<FooterProps> = ({ className = '' }) => {
  const currentYear = new Date().getFullYear();

  return (
    <Box
      component="footer"
      className={`app-footer ${className}`}
      px="md"
      py="sm"
    >
      <Group justify="center" gap="xs">
        <Text size="sm" c="dimmed">
          {`© ${currentYear} ${BRAND.fullName}`}
        </Text>
        <Text size="sm" c="dimmed">
          •
        </Text>
        <Anchor
          href="https://github.com/afairgiant/MediKeep"
          target="_blank"
          rel="noopener noreferrer"
          size="sm"
          c="dimmed"
          style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
        >
          <IconBrandGithub size={16} />
          {/* eslint-disable-next-line i18next/no-literal-string -- upstream project name */}
          {'MediKeep'}
        </Anchor>
      </Group>
    </Box>
  );
};

export default Footer;
