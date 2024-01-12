// Copyright (C) 2023 Checkmk GmbH - License: GNU General Public License v2
// This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
// conditions defined in the file COPYING, which is part of this source code package.

use anyhow::Result;
use std::collections::HashMap;

pub const UTC_DATE_FIELD: &str = "utc_date";

#[derive(Hash, PartialEq, Eq, Debug)]
pub enum Id {
    ComputerName,
    Mirroring,
    Jobs,
    AvailabilityGroups,
    InstanceProperties,
    UtcEntry,
    ClusterActiveNodes,
    ClusterNodes,
    IsClustered,
    DatabaseNames,
    Databases,
    Datafiles,
    Backup,
    SpaceUsed,
    CounterEntries,
    Connections,
    TransactionLogs,
    BadQuery,
    WaitingTasks,
    BlockingSessions,
    Counters,
    Clusters,
}

mod query {
    // TODO(sk): replace with "SELECT SERVERPROPERTY( 'MachineName' ) as MachineName"
    pub const COMPUTER_NAME: &str = r"DECLARE @ComputerName NVARCHAR(200);
DECLARE @main_key NVARCHAR(200) = 'SYSTEM\CurrentControlSet\Control\ComputerName\ComputerName';
EXECUTE xp_regread
    @rootkey = 'HKEY_LOCAL_MACHINE',
    @key = @main_key,
    @value_name = 'ComputerName',
    @value = @ComputerName OUTPUT;
  Select @ComputerName as 'ComputerName'
";
    /// Script to be run in SQL instance
    pub const WINDOWS_REGISTRY_INSTANCES_BASE: &str = r"
DECLARE @GetInstances TABLE
( Value nvarchar(100),
 InstanceNames nvarchar(100),
 Data nvarchar(100))

DECLARE @GetAll TABLE
( Value nvarchar(100),
 InstanceNames nvarchar(100),
 InstanceIds nvarchar(100),
 EditionNames nvarchar(100),
 VersionNames nvarchar(100),
 ClusterNames nvarchar(100),
 Ports nvarchar(100),
 DynamicPorts nvarchar(100),
 Data nvarchar(100))

Insert into @GetInstances
EXECUTE xp_regread
  @rootkey = 'HKEY_LOCAL_MACHINE',
  @key = 'SOFTWARE\Microsoft\Microsoft SQL Server',
  @value_name = 'InstalledInstances'

DECLARE @InstanceName NVARCHAR(100);

-- Cursor to iterate through the instance names
DECLARE instance_cursor CURSOR FOR
SELECT InstanceNames FROM @GetInstances;

OPEN instance_cursor;

-- Loop through all instances
FETCH NEXT FROM instance_cursor INTO @InstanceName;

WHILE @@FETCH_STATUS = 0
BEGIN
    DECLARE @InstanceId NVARCHAR(100);
    DECLARE @main_key NVARCHAR(200) = 'SOFTWARE\Microsoft\Microsoft SQL Server\Instance Names\SQL';
    EXECUTE xp_regread
        @rootkey = 'HKEY_LOCAL_MACHINE',
        @key = @main_key,
        @value_name = @InstanceName,
        @value = @InstanceId OUTPUT;

    -- You'll need to construct the key path using the instance name
    DECLARE @setup_key NVARCHAR(200) = 'SOFTWARE\Microsoft\Microsoft SQL Server\' + @InstanceId + '\Setup';
    DECLARE @cluster_key NVARCHAR(200) = 'SOFTWARE\Microsoft\Microsoft SQL Server\' + @InstanceId + '\Cluster';
    DECLARE @port_key NVARCHAR(200) = 'SOFTWARE\Microsoft\Microsoft SQL Server\' + @InstanceId + '\MSSQLServer\SuperSocketNetLib\TCP\IPAll';

    DECLARE @Edition NVARCHAR(100);
    EXECUTE xp_regread
        @rootkey = 'HKEY_LOCAL_MACHINE',
        @key = @setup_key,
        @value_name = 'Edition',
        @value = @Edition OUTPUT;

    DECLARE @Version NVARCHAR(100);
    EXECUTE xp_regread
        @rootkey = 'HKEY_LOCAL_MACHINE',
        @key = @setup_key,
        @value_name = 'Version',
        @value = @Version OUTPUT;

    DECLARE @ClusterName NVARCHAR(100);
    EXECUTE xp_regread
        @rootkey = 'HKEY_LOCAL_MACHINE',
        @key = @cluster_key,
        @value_name = 'ClusterName',
        @value = @ClusterName OUTPUT;

    DECLARE @Port NVARCHAR(100);
    EXECUTE xp_regread
        @rootkey = 'HKEY_LOCAL_MACHINE',
        @key = @port_key,
        @value_name = 'tcpPort',
        @value = @Port OUTPUT;

    DECLARE @DynamicPort NVARCHAR(100);
    EXECUTE xp_regread
        @rootkey = 'HKEY_LOCAL_MACHINE',
        @key = @port_key,
        @value_name = 'TcpDynamicPorts',
        @value = @DynamicPort OUTPUT;
    
    insert into @GetAll(InstanceNames, InstanceIds, EditionNames, VersionNames, ClusterNames, Ports, DynamicPorts) Values( @InstanceName, @InstanceId, @Edition, @Version, @ClusterName, @Port, @DynamicPort )
    
    -- Get the next instance
    FETCH NEXT FROM instance_cursor INTO @InstanceName;
END

CLOSE instance_cursor;
DEALLOCATE instance_cursor;

SELECT InstanceNames, InstanceIds, EditionNames, VersionNames, ClusterNames,Ports, DynamicPorts FROM @GetAll;";

    pub const UTC_ENTRY: &str = "SELECT CONVERT(varchar, GETUTCDATE(), 20) as utc_date";

    pub const COUNTERS_ENTRIES: &str =
        "SELECT counter_name, object_name, instance_name, cntr_value \
     FROM sys.dm_os_performance_counters \
     WHERE object_name NOT LIKE '%Deprecated%'";

    /// used only for testing: it is difficult to get blocked tasks in reality
    pub const WAITING_TASKS: &str = "SELECT cast(session_id as varchar) as session_id, \
            cast(wait_duration_ms as bigint) as wait_duration_ms, \
            wait_type, \
            cast(blocking_session_id as varchar) as blocking_session_id \
    FROM sys.dm_os_waiting_tasks";

    pub const DATABASE_NAMES: &str = "SELECT name FROM sys.databases";
    pub const SPACE_USED: &str = "EXEC sp_spaceused";

    pub const BACKUP: &str = r"DECLARE @HADRStatus sql_variant; DECLARE @SQLCommand nvarchar(max);
SET @HADRStatus = (SELECT SERVERPROPERTY ('IsHadrEnabled'));
IF (@HADRStatus IS NULL or @HADRStatus <> 1)
BEGIN
    SET @SQLCommand = 'SELECT CONVERT(VARCHAR, DATEADD(s, DATEDIFF(s, ''19700101'', MAX(backup_finish_date)), ''19700101''), 120) AS last_backup_date,
    type, machine_name, ''True'' as is_primary_replica, ''1'' as is_local, '''' as replica_id,database_name FROM msdb.dbo.backupset
    WHERE UPPER(machine_name) = UPPER(CAST(SERVERPROPERTY(''Machinename'') AS VARCHAR))
    GROUP BY type, machine_name,database_name '
END
ELSE
BEGIN
    SET @SQLCommand = 'SELECT CONVERT(VARCHAR, DATEADD(s, DATEDIFF(s, ''19700101'', MAX(b.backup_finish_date)), ''19700101''), 120) AS last_backup_date,
    b.type, b.machine_name, isnull(rep.is_primary_replica,0) as is_primary_replica, rep.is_local, isnull(convert(varchar(40), rep.replica_id), '''') AS replica_id,database_name 
    FROM msdb.dbo.backupset b
    LEFT OUTER JOIN sys.databases db ON b.database_name = db.name
    LEFT OUTER JOIN sys.dm_hadr_database_replica_states rep ON db.database_id = rep.database_id
    WHERE (rep.is_local is null or rep.is_local = 1)
    AND (rep.is_primary_replica is null or rep.is_primary_replica = ''True'') and UPPER(machine_name) = UPPER(CAST(SERVERPROPERTY(''Machinename'') AS VARCHAR))
    GROUP BY type, rep.replica_id, rep.is_primary_replica, rep.is_local, b.database_name, b.machine_name, rep.synchronization_state, rep.synchronization_health'
END
EXEC (@SQLCommand)
";

    pub const TRANSACTION_LOGS: &str = "SELECT name, physical_name,\
  cast(max_size/128 as bigint) as MaxSize,\
  cast(size/128 as bigint) as AllocatedSize,\
  cast(FILEPROPERTY (name, 'spaceused')/128 as bigint) as UsedSize,\
  case when max_size = '-1' then '1' else '0' end as Unlimited \
 FROM sys.database_files WHERE type_desc = 'LOG'";

    pub const DATAFILES: &str = "SELECT name, physical_name,\
  cast(max_size/128 as bigint) as MaxSize,\
  cast(size/128 as bigint) as AllocatedSize,\
  cast(FILEPROPERTY (name, 'spaceused')/128 as bigint) as UsedSize,\
  case when max_size = '-1' then '1' else '0' end as Unlimited \
FROM sys.database_files WHERE type_desc = 'ROWS'";

    pub const DATABASES: &str = "SELECT name, \
cast(DATABASEPROPERTYEX(name, 'Status') as varchar) AS Status, \
  cast(DATABASEPROPERTYEX(name, 'Recovery') as varchar) AS Recovery, \
  cast(DATABASEPROPERTYEX(name, 'IsAutoClose') as bigint) AS auto_close, \
  cast(DATABASEPROPERTYEX(name, 'IsAutoShrink') as bigint) AS auto_shrink \
FROM master.dbo.sysdatabases";

    pub const IS_CLUSTERED: &str =
        "SELECT cast( SERVERPROPERTY('IsClustered') as varchar) AS is_clustered";
    pub const CLUSTER_NODES: &str = "SELECT nodename FROM sys.dm_os_cluster_nodes";
    pub const CLUSTER_ACTIVE_NODES: &str =
        "SELECT cast(SERVERPROPERTY('ComputerNamePhysicalNetBIOS') as varchar) AS active_node";

    pub const CONNECTIONS: &str = "SELECT name AS DbName, \
      cast((SELECT COUNT(dbid) AS Num_Of_Connections FROM sys.sysprocesses WHERE dbid > 0 AND name = DB_NAME(dbid) GROUP BY dbid ) as bigint) AS NumberOfConnections  \
FROM sys.databases";

    pub const JOBS: &str = "SELECT \
  sj.job_id AS job_id, \
  sj.name AS job_name, \
  sj.enabled AS job_enabled, \
  CAST(sjs.next_run_date AS VARCHAR(8)) AS next_run_date, \
  CAST(sjs.next_run_time AS VARCHAR(6)) AS next_run_time, \
  sjserver.last_run_outcome, \
  sjserver.last_outcome_message, \
  CAST(sjserver.last_run_date AS VARCHAR(8)) AS last_run_date, \
  CAST(sjserver.last_run_time AS VARCHAR(6)) AS last_run_time, \
  sjserver.last_run_duration, \
  ss.enabled AS schedule_enabled, \
  CONVERT(VARCHAR, CURRENT_TIMESTAMP, 20) AS server_current_time \
FROM dbo.sysjobs sj \
LEFT JOIN dbo.sysjobschedules sjs ON sj.job_id = sjs.job_id \
LEFT JOIN dbo.sysjobservers sjserver ON sj.job_id = sjserver.job_id \
LEFT JOIN dbo.sysschedules ss ON sjs.schedule_id = ss.schedule_id \
ORDER BY sj.name, \
         sjs.next_run_date ASC, \
         sjs.next_run_time ASC \
";

    pub const MIRRORING: &str = "SELECT @@SERVERNAME as server_name, \
  DB_NAME(database_id) AS [database_name], \
  mirroring_state, \
  mirroring_state_desc, \
  mirroring_role, \
  mirroring_role_desc, \
  mirroring_safety_level, \
  mirroring_safety_level_desc, \
  mirroring_partner_name, \
  mirroring_partner_instance, \
  mirroring_witness_name, \
  mirroring_witness_state, \
  mirroring_witness_state_desc \
FROM sys.database_mirroring \
WHERE mirroring_state IS NOT NULL";

    pub const AVAILABILITY_GROUP: &str = "SELECT \
  GroupsName.name, \
  Groups.primary_replica, \
  Groups.synchronization_health, \
  Groups.synchronization_health_desc, \
  Groups.primary_recovery_health_desc \
FROM sys.dm_hadr_availability_group_states Groups \
INNER JOIN master.sys.availability_groups GroupsName ON Groups.group_id = GroupsName.group_id";

    pub const INSTANCE_PROPERTIES: &str = "SELECT \
    cast(SERVERPROPERTY( 'InstanceName' ) as varchar)as InstanceName, \
    cast(SERVERPROPERTY( 'ProductVersion' ) as varchar) as ProductVersion, \
    cast(SERVERPROPERTY( 'MachineName' ) as varchar) as MachineName, \
    cast(SERVERPROPERTY( 'Edition' ) as varchar) as Edition, \
    cast(SERVERPROPERTY( 'ProductLevel' ) as varchar) as ProductLevel, \
    cast(SERVERPROPERTY( 'ComputerNamePhysicalNetBIOS' ) as varchar) as NetBios";

    #[allow(dead_code)]
    pub const BAD_QUERY: &str = "SELEC name FROM sys.databases";
}

pub fn get_win_registry_instances_query() -> String {
    query::WINDOWS_REGISTRY_INSTANCES_BASE.to_string()
}

pub fn get_wow64_32_registry_instances_query() -> String {
    query::WINDOWS_REGISTRY_INSTANCES_BASE
        .to_string()
        .replace(r"SOFTWARE\Microsoft\", r"SOFTWARE\WOW6432Node\Microsoft\")
}
pub fn _get_blocking_sessions_query() -> String {
    format!("{} WHERE blocking_session_id <> 0 ", query::WAITING_TASKS).to_string()
}

lazy_static::lazy_static! {
    static ref BLOCKING_SESSIONS: String = format!("{} WHERE blocking_session_id <> 0 ", query::WAITING_TASKS).to_string();
    static ref COUNTERS: String = format!("{};{};", query::UTC_ENTRY, query::COUNTERS_ENTRIES  ).to_string();
    static ref CLUSTERS: String = format!("{};{};", query::CLUSTER_NODES, query::CLUSTER_ACTIVE_NODES  ).to_string();
    static ref QUERY_MAP: HashMap<Id, &'static str> = HashMap::from([
        (Id::ComputerName, query::COMPUTER_NAME),
        (Id::Mirroring, query::MIRRORING),
        (Id::Jobs, query::JOBS),
        (Id::AvailabilityGroups, query::AVAILABILITY_GROUP),
        (Id::InstanceProperties, query::INSTANCE_PROPERTIES),
        (Id::UtcEntry, query::UTC_ENTRY),
        (Id::ClusterActiveNodes, query::CLUSTER_ACTIVE_NODES),
        (Id::ClusterNodes, query::CLUSTER_NODES),
        (Id::IsClustered, query::IS_CLUSTERED),
        (Id::DatabaseNames, query::DATABASE_NAMES),
        (Id::Databases, query::DATABASES),
        (Id::Datafiles, query::DATAFILES),
        (Id::Backup, query::BACKUP),
        (Id::SpaceUsed, query::SPACE_USED),
        (Id::CounterEntries, query::COUNTERS_ENTRIES),
        (Id::Connections, query::CONNECTIONS),
        (Id::TransactionLogs, query::TRANSACTION_LOGS),
        (Id::BadQuery, query::BAD_QUERY),
        (Id::WaitingTasks, query::WAITING_TASKS), // used only in tests now
        (Id::BlockingSessions, BLOCKING_SESSIONS.as_str()),
        (Id::Counters, COUNTERS.as_str()),
        (Id::Clusters, CLUSTERS.as_str()),
    ]);
}

pub fn get_query(query_id: &Id) -> Result<&'static str> {
    QUERY_MAP
        .get(query_id)
        .copied()
        .ok_or(anyhow::anyhow!("Query for {:?} not found", query_id))
}
