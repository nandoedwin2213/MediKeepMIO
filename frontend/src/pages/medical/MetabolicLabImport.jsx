import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Container,
  FileButton,
  Group,
  NumberInput,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Textarea,
  ThemeIcon,
  Title,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconAlertTriangle,
  IconCheck,
  IconDownload,
  IconFileImport,
  IconSearch,
  IconUpload,
} from '@tabler/icons-react';
import { PageHeader } from '../../components';
import { usePatientWithStaticData } from '../../hooks/useGlobalData';
import metabolicApi from '../../services/api/metabolicApi';
import logger from '../../services/logger';

const TEMPLATE = [
  'Prueba;Valor;Unidad;Referencia',
  'Glucosa en ayunas;95;mg/dL;70 - 100',
  'Insulina;12;µUI/mL;2.6 - 24.9',
  'HbA1c;5.6;%;4.0 - 5.6',
  'Triglicéridos;150;mg/dL;< 150',
  'Colesterol HDL;45;mg/dL;> 40',
  'Colesterol LDL;120;mg/dL;< 130',
  'Colesterol total;190;mg/dL;< 200',
  'TGP (ALT);25;U/L;0 - 41',
  'TGO (AST);22;U/L;0 - 40',
  'GGT;30;U/L;8 - 61',
  'Creatinina;0.9;mg/dL;0.7 - 1.2',
  'Ácido úrico;5.5;mg/dL;3.5 - 7.2',
].join('\n');

const WARN_COLORS = {
  implausible: 'red',
  unknown_unit: 'red',
  unit_assumed: 'yellow',
  qualifier: 'yellow',
  duplicate: 'gray',
};

const today = () => new Date().toISOString().slice(0, 10);

function downloadText(content, filename, type) {
  const url = window.URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

function SectionTitle({ icon: Icon, children }) {
  return (
    <Group gap="sm" mb="sm" wrap="nowrap">
      <ThemeIcon variant="light" radius="md">
        <Icon size={18} />
      </ThemeIcon>
      <Title order={4}>{children}</Title>
    </Group>
  );
}

const MetabolicLabImport = () => {
  const { t } = useTranslation('medical');
  const l = (key, opts) => t(`metabolic.labs.${key}`, opts);
  const { patient } = usePatientWithStaticData();
  const patientId = patient?.patient?.id;

  const [catalog, setCatalog] = useState([]);
  const [text, setText] = useState('');
  const [file, setFile] = useState(null);
  const [parsing, setParsing] = useState(false);
  const [parsed, setParsed] = useState(null);
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ date: today(), name: '', facility: '' });
  const [importing, setImporting] = useState(false);
  const [done, setDone] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    metabolicApi
      .getLabCatalog(controller.signal)
      .then(data => !controller.signal.aborted && setCatalog(data || []))
      .catch(err => {
        if (!controller.signal.aborted)
          logger.error('metabolic_lab_catalog_failed', { error: err?.message });
      });
    return () => controller.abort();
  }, []);

  const byVar = useMemo(
    () => Object.fromEntries(catalog.map(c => [c.variable, c])),
    [catalog]
  );
  const selected = rows.filter(r => r.selected);

  const analyse = async () => {
    setParsing(true);
    setError(null);
    setDone(null);
    try {
      const out = await metabolicApi.parseLabs(patientId, { text, file });
      setParsed(out);
      setRows(out.rows.map((r, i) => ({ ...r, id: i })));
      setMeta(m => ({
        ...m,
        date: out.suggested_date || m.date,
        name: m.name || l('defaultName'),
      }));
    } catch (err) {
      logger.error('metabolic_lab_parse_failed', { error: err?.message });
      setError(l('parseError'));
    } finally {
      setParsing(false);
    }
  };

  const update = (id, patch) =>
    setRows(prev =>
      prev.map(r =>
        r.id === id
          ? {
              ...r,
              ...patch,
              warnings:
                'value' in patch || 'unit' in patch
                  ? r.warnings.filter(w => w === 'duplicate')
                  : r.warnings,
            }
          : r
      )
    );

  const submit = async () => {
    setImporting(true);
    setError(null);
    try {
      const out = await metabolicApi.importLabs(patientId, {
        collected_on: meta.date,
        name: meta.name || l('defaultName'),
        facility: meta.facility || null,
        rows: selected.map(r => ({
          variable: r.variable,
          value: r.value,
          unit: r.unit,
          ref_min: r.ref_min === '' ? null : r.ref_min,
          ref_max: r.ref_max === '' ? null : r.ref_max,
          ref_text: r.ref_text,
        })),
      });
      setDone(out);
      setParsed(null);
      setRows([]);
      setText('');
      setFile(null);
      notifications.show({
        color: 'teal',
        message: l('imported', { count: out.imported }),
      });
    } catch (err) {
      logger.error('metabolic_lab_import_failed', { error: err?.message });
      setError(l('importError'));
    } finally {
      setImporting(false);
    }
  };

  const invalid = selected.some(
    r => !r.unit || !(r.value > 0) || r.warnings.includes('implausible')
  );

  const includeBox = r => (
    <Checkbox
      aria-label={l('include')}
      checked={r.selected}
      onChange={e =>
        update(r.id, {
          selected: e.currentTarget.checked,
        })
      }
    />
  );
  const testCell = r => (
    <>
      <Group gap={6}>
        <Text fw={600}>{t(`metabolic.indicators.${r.variable}`)}</Text>
        <Badge size="xs" variant="outline" title={l('loincHint')}>
          LOINC {r.loinc}
        </Badge>
      </Group>
      <Text size="xs" c="dimmed" lineClamp={1}>
        {r.line}
      </Text>
      {r.warnings.length > 0 && (
        <Group gap={4} mt={4}>
          {r.warnings.map(w => (
            <Badge
              key={w}
              size="sm"
              color={WARN_COLORS[w]}
              variant="light"
              style={{ textTransform: 'none' }}
            >
              {l(`warnings.${w}`)}
            </Badge>
          ))}
        </Group>
      )}
    </>
  );
  const valueInput = r => (
    <NumberInput
      aria-label={l('cols.value')}
      value={r.value}
      min={0}
      decimalScale={2}
      hideControls
      onChange={v => update(r.id, { value: v })}
    />
  );
  const unitInput = r => (
    <Select
      aria-label={l('cols.unit')}
      data={byVar[r.variable]?.units || []}
      value={r.unit}
      placeholder={l('chooseUnit')}
      onChange={v => update(r.id, { unit: v })}
      allowDeselect={false}
    />
  );
  const rangeInputs = r => (
    <Group gap={4} wrap="nowrap">
      <NumberInput
        aria-label={l('refMin')}
        placeholder={l('refMin')}
        value={r.ref_min ?? ''}
        decimalScale={2}
        hideControls
        onChange={v => update(r.id, { ref_min: v, ref_text: null })}
      />
      <Text c="dimmed">–</Text>
      <NumberInput
        aria-label={l('refMax')}
        placeholder={l('refMax')}
        value={r.ref_max ?? ''}
        decimalScale={2}
        hideControls
        onChange={v => update(r.id, { ref_max: v, ref_text: null })}
      />
    </Group>
  );

  return (
    <Container size="xl" py="md" className="silho-ir-page">
      <PageHeader title={l('title')} icon="🧪" />
      <Text c="dimmed" mt="md">
        {l('subtitle')}
      </Text>
      {!patientId && (
        <Alert color="blue" mt="md">
          {t('metabolic.selectPatient')}
        </Alert>
      )}
      {error && (
        <Alert color="red" mt="md" icon={<IconAlertTriangle size={18} />}>
          {error}
        </Alert>
      )}
      {done && (
        <Alert color="teal" mt="md" icon={<IconCheck size={18} />}>
          <Text fw={600}>{l('imported', { count: done.imported })}</Text>
          {typeof done.score?.value === 'number' && (
            <Text size="sm">{l('newScore', { score: done.score.value })}</Text>
          )}
          <Group gap="sm" mt="xs">
            <Button component={Link} to="/metabolic-risk" size="xs">
              {l('seeRisk')}
            </Button>
            <Button
              component={Link}
              to="/lab-results"
              size="xs"
              variant="light"
            >
              {l('seeLabs')}
            </Button>
          </Group>
        </Alert>
      )}

      {patientId && (
        <Stack gap="lg" mt="md">
          <Card withBorder radius="lg" padding="lg">
            <SectionTitle icon={IconFileImport}>{l('step1')}</SectionTitle>
            <Text size="sm" c="dimmed" mb="sm">
              {l('step1Hint')}
            </Text>
            <Textarea
              aria-label={l('pasteLabel')}
              placeholder={l('pastePlaceholder')}
              autosize
              minRows={6}
              maxRows={16}
              value={text}
              onChange={e => {
                setText(e.currentTarget.value);
                setFile(null);
              }}
              styles={{ input: { fontFamily: 'monospace' } }}
            />
            <Group mt="sm" gap="sm">
              <FileButton
                onChange={f => {
                  setFile(f);
                  if (f) setText('');
                }}
                accept=".pdf,.csv,.txt,application/pdf,text/csv,text/plain"
              >
                {props => (
                  <Button
                    {...props}
                    variant="light"
                    leftSection={<IconUpload size={16} />}
                  >
                    {l('upload')}
                  </Button>
                )}
              </FileButton>
              {file && (
                <Badge
                  variant="light"
                  size="lg"
                  style={{ textTransform: 'none' }}
                >
                  {file.name}
                </Badge>
              )}
              <Button
                leftSection={<IconSearch size={16} />}
                onClick={analyse}
                loading={parsing}
                disabled={!file && !text.trim()}
              >
                {l('analyse')}
              </Button>
              <Button
                variant="subtle"
                leftSection={<IconDownload size={16} />}
                onClick={() =>
                  downloadText(
                    TEMPLATE,
                    'silho-plantilla-laboratorio.csv',
                    'text/csv'
                  )
                }
              >
                {l('template')}
              </Button>
            </Group>
          </Card>

          {parsed && (
            <Card withBorder radius="lg" padding="lg">
              <SectionTitle icon={IconCheck}>{l('step2')}</SectionTitle>
              <Text size="sm" mb="sm">
                {l('found', { count: rows.length })}
                {parsed.unrecognized > 0 &&
                  ` ${l('unrecognized', { count: parsed.unrecognized })}`}
              </Text>
              {rows.length === 0 ? (
                <Alert color="yellow">{l('nothingFound')}</Alert>
              ) : (
                <>
                  <SimpleGrid cols={{ base: 1, sm: 3 }} mb="md">
                    <TextInput
                      type="date"
                      label={l('date')}
                      value={meta.date}
                      max={today()}
                      onChange={e =>
                        setMeta(m => ({ ...m, date: e.currentTarget.value }))
                      }
                      required
                    />
                    <TextInput
                      label={l('name')}
                      value={meta.name}
                      maxLength={120}
                      onChange={e =>
                        setMeta(m => ({ ...m, name: e.currentTarget.value }))
                      }
                    />
                    <TextInput
                      label={l('facility')}
                      value={meta.facility}
                      maxLength={120}
                      onChange={e =>
                        setMeta(m => ({
                          ...m,
                          facility: e.currentTarget.value,
                        }))
                      }
                    />
                  </SimpleGrid>
                  <Stack gap="sm" hiddenFrom="sm">
                    {rows.map(r => (
                      <Card key={r.id} withBorder padding="sm" radius="md">
                        <Group align="flex-start" wrap="nowrap" gap="sm">
                          {includeBox(r)}
                          <div style={{ minWidth: 0, flex: 1 }}>
                            {testCell(r)}
                          </div>
                        </Group>
                        <SimpleGrid cols={2} spacing="xs" mt="sm">
                          {valueInput(r)}
                          {unitInput(r)}
                        </SimpleGrid>
                        <Text size="xs" c="dimmed" mt="xs" mb={4}>
                          {l('cols.reference')}
                        </Text>
                        {rangeInputs(r)}
                      </Card>
                    ))}
                  </Stack>
                  <Table.ScrollContainer minWidth={760} visibleFrom="sm">
                    <Table verticalSpacing="sm" striped>
                      <Table.Thead>
                        <Table.Tr>
                          <Table.Th />
                          <Table.Th>{l('cols.test')}</Table.Th>
                          <Table.Th>{l('cols.value')}</Table.Th>
                          <Table.Th>{l('cols.unit')}</Table.Th>
                          <Table.Th>{l('cols.reference')}</Table.Th>
                        </Table.Tr>
                      </Table.Thead>
                      <Table.Tbody>
                        {rows.map(r => (
                          <Table.Tr key={r.id}>
                            <Table.Td>{includeBox(r)}</Table.Td>
                            <Table.Td>{testCell(r)}</Table.Td>
                            <Table.Td w={120}>{valueInput(r)}</Table.Td>
                            <Table.Td w={140}>{unitInput(r)}</Table.Td>
                            <Table.Td w={200}>{rangeInputs(r)}</Table.Td>
                          </Table.Tr>
                        ))}
                      </Table.Tbody>
                    </Table>
                  </Table.ScrollContainer>
                  <Text size="xs" c="dimmed" mt="sm">
                    {l('reviewHint')}
                  </Text>
                  <Group justify="flex-end" mt="md">
                    <Button
                      onClick={submit}
                      loading={importing}
                      disabled={!selected.length || invalid || !meta.date}
                      leftSection={<IconCheck size={16} />}
                    >
                      {l('import', { count: selected.length })}
                    </Button>
                  </Group>
                </>
              )}
            </Card>
          )}
        </Stack>
      )}
    </Container>
  );
};

export default MetabolicLabImport;
